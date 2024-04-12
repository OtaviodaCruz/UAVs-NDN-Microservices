#include "tcp_face.h"

#include <boost/bind.hpp>

#include <sstream>

#include "../log/logger.h"

static void findPackets(std::string &stream, std::vector<ndn::Interest> &interests, std::vector<ndn::Data> &datas);

TcpFace::TcpFace(boost::asio::io_service &ios, std::string host, uint16_t port)
        : Face(ios)
        , _skip_connect(false)
        , _endpoint(boost::asio::ip::address::from_string(host), port)
        , _socket(ios)
        , _strand(ios)
        , _timer(ios) {
}

TcpFace::TcpFace(boost::asio::io_service &ios, const boost::asio::ip::tcp::endpoint &endpoint)
        : Face(ios)
        , _skip_connect(false)
        , _endpoint(endpoint)
        , _socket(ios)
        , _strand(ios)
        , _timer(ios) {
}

TcpFace::TcpFace(boost::asio::ip::tcp::socket &&socket)
        : Face(socket.get_io_service())
        , _skip_connect(true)
        , _endpoint(socket.remote_endpoint())
        , _socket(std::move(socket))
        , _strand(socket.get_io_service())
        , _timer(socket.get_io_service()) {

}

std::string TcpFace::getUnderlyingProtocol() const {
    return "TCP";
}

std::string TcpFace::getUnderlyingEndpoint() const {
    std::stringstream ss;
    ss << _endpoint;
    return ss.str();
}

void TcpFace::open(const InterestCallback &interest_callback,
                   const DataCallback &data_callback,
                   const ErrorCallback &error_callback) {
    _interest_callback = interest_callback;
    _data_callback = data_callback;
    _error_callback = error_callback;
    if(!_skip_connect && !_is_connected) {
        connect();
    } else {
        _is_connected = true;
        read();
    }
}

void TcpFace::close() {
    _is_connected = false;
    _socket.close();
}

void TcpFace::send(const std::string &message) {
    _strand.post(boost::bind(&TcpFace::sendImpl, shared_from_this(), message));
}

void TcpFace::send(const ndn::Interest &interest) {
    _strand.post(boost::bind(&TcpFace::sendImpl, shared_from_this(), std::string((const char *)interest.wireEncode().wire(), interest.wireEncode().size())));
}

void TcpFace::send(const ndn::Data &data) {
    _strand.post(boost::bind(&TcpFace::sendImpl, shared_from_this(), std::string((const char *)data.wireEncode().wire(), data.wireEncode().size())));
}

void TcpFace::connect() {
    _timer.expires_from_now(boost::posix_time::seconds(2));
    _timer.async_wait(_strand.wrap(boost::bind(&TcpFace::timerHandler, shared_from_this(), _1)));
    _socket.async_connect(_endpoint, _strand.wrap(boost::bind(&TcpFace::connectHandler, shared_from_this(), _1)));
}

void TcpFace::connectHandler(const boost::system::error_code &err) {
    _timer.cancel();
    if (!err) {
        std::stringstream ss;
        ss << "TCP face with ID = " << _face_id << " successfully connected to tcp://" << _endpoint;
        logger::log(logger::INFO, ss.str());
        _is_connected = true;
        read();
    } else {
        std::stringstream ss;
        ss << "failed to connect to " << _endpoint;
        logger::log(logger::ERROR, ss.str());
        _error_callback(shared_from_this());
    }
}

void TcpFace::reconnect(size_t remaining_attempt) {
    std::stringstream ss;
    ss << "try to reconnect to " << _endpoint;
    logger::log(logger::INFO, ss.str());
    _socket.close();
    _timer.expires_from_now(boost::posix_time::seconds(2));
    _timer.async_wait(_strand.wrap(boost::bind(&TcpFace::timerHandler, shared_from_this(), _1)));
    _socket.async_connect(_endpoint, boost::bind(&TcpFace::reconnectHandler, shared_from_this(), _1, remaining_attempt - 1));
}

void TcpFace::reconnectHandler(const boost::system::error_code &err, size_t remaining_attempt) {
    _timer.cancel();
    if(!err) {
        read();
        if(_queue_in_use) {
            write();
        }
    } else if (remaining_attempt > 0 && _is_connected) {
        std::stringstream ss;
        ss << "wait 1s before next reconnection to " << _endpoint;
        logger::log(logger::INFO, ss.str());
        _timer.expires_from_now(boost::posix_time::seconds(1));
        _timer.async_wait(boost::bind(&TcpFace::reconnect, shared_from_this(), remaining_attempt));
    } else {
        std::stringstream ss;
        ss << "failed to reconnect to " << _endpoint;
        logger::log(logger::ERROR, ss.str());
        _error_callback(shared_from_this());
    }
}

void TcpFace::read() {
    boost::asio::async_read(_socket, boost::asio::buffer(_buffer, BUFFER_SIZE), boost::asio::transfer_at_least(1),
                            boost::bind(&TcpFace::readHandler, shared_from_this(), _1, _2));
}

void TcpFace::readHandler(const boost::system::error_code &err, size_t bytes_transferred) {
    if(!err) {
        _stream.append(_buffer, bytes_transferred);
        std::vector<ndn::Interest> interests;
        std::vector<ndn::Data> datas;
        findPackets(_stream, interests, datas);

        for (const auto &interest : interests) {
            _interest_callback(shared_from_this(), interest);
        }

        for (const auto &data : datas) {
            _data_callback(shared_from_this(), data);
        }

        read();
    } else {
        if(!_skip_connect && _is_connected) {
            std::stringstream ss;
            ss << "lost connection to " << _endpoint;
            logger::log(logger::WARNING, ss.str());
            reconnect(3);
        } else {
            _error_callback(shared_from_this());
        }
    }
}

void TcpFace::sendImpl(const std::string &message) {
    _queue.push_back(message);
    if (_queue_in_use) {
        return;
    }

    _queue_in_use = true;
    write();
}

void TcpFace::write() {
    const std::string& message = _queue.front();
    boost::asio::async_write(_socket, boost::asio::buffer(message), _strand.wrap(boost::bind(&TcpFace::writeHandler, shared_from_this(), _1, _2)));
}

void TcpFace::writeHandler(const boost::system::error_code &err, size_t bytesTransferred) {
    if(!err) {
        _queue.pop_front();

        if (!_queue.empty()) {
            write();
        } else {
            _queue_in_use = false;
        }
    }
}

void TcpFace::timerHandler(const boost::system::error_code &err) {
    if (!err) {
        _error_callback(shared_from_this());
    }
}

static void findPackets(std::string &stream, std::vector<ndn::Interest> &interests, std::vector<ndn::Data> &datas) {
    static const char delimiters[] = {0x05 /*Interest*/, 0x06 /*Data*/, 0x64 /*LpHeader*/};
    // find as much packets as possible in the stream
    try {
        do {
            // packet start with the packetDelimiter (for ndn 0x05 or 0x06) so we remove any starting bytes that is
            // not packetDelimiter
            stream.erase(0, stream.find_first_of(delimiters));

            // select the length of the size according to tlv format (0, 2, 4 or 8 bytes to read)
            uint64_t size = 0;
            switch ((uint8_t)stream[1]) {
                default:
                    size += (uint8_t)stream[1];
                    size += 2;
                    break;
                case 0xFD:
                    size += (uint8_t)stream[2];
                    size <<= 8;
                    size += (uint8_t)stream[3];
                    size += 4;
                    break;
                case 0xFE:
                    size += (uint8_t)stream[2];
                    size <<= 8;
                    size += (uint8_t)stream[3];
                    size <<= 8;
                    size += (uint8_t)stream[4];
                    size <<= 8;
                    size += (uint8_t)stream[5];
                    size += 6;
                    break;
                case 0xFF:
                    size += (uint8_t)stream[2];
                    size <<= 8;
                    size += (uint8_t)stream[3];
                    size <<= 8;
                    size += (uint8_t)stream[4];
                    size <<= 8;
                    size += (uint8_t)stream[5];
                    size <<= 8;
                    size += (uint8_t)stream[6];
                    size <<= 8;
                    size += (uint8_t)stream[7];
                    size <<= 8;
                    size += (uint8_t)stream[8];
                    size <<= 8;
                    size += (uint8_t)stream[9];
                    size += 10;
                    break;
            }

            // check if the stream have enough bytes else wait for more data in the stream
            if (size > ndn::MAX_NDN_PACKET_SIZE) {
                stream.erase(0, 1);
            } else if (size <= stream.size()) {
                // try to build the packet object then remove the read bytes from stream, if fail remove the first
                // byte in order to find the next delimiter
                try {
                    switch (stream[0]) {
                        case 0x05:
                            interests.emplace_back(ndn::Block((uint8_t*)stream.c_str(), size));
                            break;
                        case 0x06:
                            datas.emplace_back(ndn::Block((uint8_t*)stream.c_str(), size));
                            break;
                        case 0x64:
                            //Lp packets not supported yet
                            break;
                        default:
                            break;
                    }
                    stream.erase(0, size);
                } catch (const std::exception &e) {
                    std::cerr << e.what() << std::endl;
                    stream.erase(0, 1);
                }
            } else {
                break;
            }
        } while (!stream.empty());
    } catch (const std::exception &e) {
        std::cerr << e.what() << std::endl;
    }
}