#include "udp_face.h"

#include <boost/bind.hpp>

#include <sstream>

UdpFace::UdpFace(boost::asio::io_service &ios, const std::string &host, uint16_t port)
        : Face(ios)
        , _endpoint(boost::asio::ip::address::from_string(host), port)
        , _socket(ios, boost::asio::ip::udp::v4())
        , _strand(ios)
        , _timer(ios) {
}

UdpFace::UdpFace(boost::asio::io_service &ios, const boost::asio::ip::udp::endpoint &endpoint)
        : Face(ios)
        , _endpoint(endpoint)
        , _socket(ios, boost::asio::ip::udp::v4())
        , _strand(ios)
        , _timer(ios) {
}

std::string UdpFace::getUnderlyingProtocol() const {
    return "UDP";
}

std::string UdpFace::getUnderlyingEndpoint() const {
    std::stringstream ss;
    ss << _endpoint;
    return ss.str();
}

void UdpFace::open(const InterestCallback &interest_callback, const DataCallback &data_callback, const ErrorCallback &error_callback) {
    _interest_callback = interest_callback;
    _data_callback = data_callback;
    _error_callback = error_callback;
    read();
}

void UdpFace::close() {
    _socket.close();
}

void UdpFace::send(const std::string &message) {
    _strand.dispatch(boost::bind(&UdpFace::sendImpl, shared_from_this(), message));
}

void UdpFace::send(const ndn::Interest &interest) {
    _strand.dispatch(boost::bind(&UdpFace::sendImpl, shared_from_this(), std::string((const char *)interest.wireEncode().wire(), interest.wireEncode().size())));
}

void UdpFace::send(const ndn::Data &data) {
    _strand.dispatch(boost::bind(&UdpFace::sendImpl, shared_from_this(), std::string((const char *)data.wireEncode().wire(), data.wireEncode().size())));
}

void UdpFace::read() {
    _socket.async_receive_from(boost::asio::buffer(_buffer, BUFFER_SIZE), _remote_endpoint,
                               boost::bind(&UdpFace::readHandler, shared_from_this(), _1, _2));
}

void UdpFace::readHandler(const boost::system::error_code &err, size_t bytes_transferred) {
    if(!err) {
        if (_remote_endpoint == _endpoint) {
            try {
                switch (_buffer[0]) {
                    case 0x00:
                        // special packet, just echoes it
                        send("0");
                        break;
                    case 0x05:
                        _interest_callback(shared_from_this(), ndn::Interest(ndn::Block((uint8_t *) _buffer, bytes_transferred)));
                        break;
                    case 0x06:
                        _data_callback(shared_from_this(), ndn::Data(ndn::Block((uint8_t *) _buffer, bytes_transferred)));
                        break;
                    default:
                        break;
                }
            } catch (const std::exception &e) {
                std::cerr << e.what() << std::endl;
            }
        }
        read();
    } else {
        std::cerr << err.message() << std::endl;
        _error_callback(shared_from_this());
    }
}

void UdpFace::sendImpl(const std::string &message) {
    _queue.push_back(message);
    if (_queue.size() == 1) {
        write();
    }
}

void UdpFace::write() {
    const std::string& message = _queue.front();
    _socket.async_send_to(boost::asio::buffer(message), _endpoint,
                          _strand.wrap(boost::bind(&UdpFace::writeHandler, shared_from_this(), _1, _2)));
}

void UdpFace::writeHandler(const boost::system::error_code &err, size_t bytesTransferred) {
    if(!err) {
        _queue.pop_front();
        if (!_queue.empty()) {
            write();
        }
    }
}