#include "udp_master_face.h"

#include <boost/bind.hpp>

#include "../log/logger.h"

UdpMasterFace::UdpSubFace::UdpSubFace(UdpMasterFace &master_face, const boost::asio::ip::udp::endpoint &endpoint)
        : Face(master_face.get_io_service())
        , _master_face(master_face)
        , _endpoint(endpoint)
        , _timer(master_face.get_io_service()) {

}

std::string UdpMasterFace::UdpSubFace::getUnderlyingProtocol() const {
    return "UDP";
}

std::string UdpMasterFace::UdpSubFace::getUnderlyingEndpoint() const {
    std::stringstream ss;
    ss << _endpoint;
    return ss.str();
}

const boost::asio::ip::udp::endpoint& UdpMasterFace::UdpSubFace::getEndpoint() {
    return _endpoint;
}

void UdpMasterFace::UdpSubFace::open(const InterestCallback &interest_callback,
                                     const DataCallback &data_callback,
                                     const ErrorCallback &error_callback) {
    _interest_callback = interest_callback;
    _data_callback = data_callback;
    _error_callback = error_callback;
    _timer.expires_from_now(boost::posix_time::seconds(3));
    _timer.async_wait(boost::bind(&UdpSubFace::timerHandler, shared_from_this(), _1, false));
}

void UdpMasterFace::UdpSubFace::close() {
    _error_callback(shared_from_this());
}

void UdpMasterFace::UdpSubFace::send(const std::string &message) {
    _timer.expires_from_now(boost::posix_time::seconds(3));
    _master_face._strand.post(boost::bind(&UdpMasterFace::sendImpl, _master_face.shared_from_this(), message, _endpoint));
}

void UdpMasterFace::UdpSubFace::send(const ndn::Interest &interest) {
    _timer.expires_from_now(boost::posix_time::seconds(3));
    _master_face._strand.post(boost::bind(&UdpMasterFace::sendImpl, _master_face.shared_from_this(), std::string((const char *)interest.wireEncode().wire(), interest.wireEncode().size()), _endpoint));
}

void UdpMasterFace::UdpSubFace::send(const ndn::Data &data) {
    _timer.expires_from_now(boost::posix_time::seconds(3));
    _master_face._strand.post(boost::bind(&UdpMasterFace::sendImpl, _master_face.shared_from_this(), std::string((const char *)data.wireEncode().wire(), data.wireEncode().size()), _endpoint));
}

void UdpMasterFace::UdpSubFace::proceedPacket(const char *buffer, size_t size) {
    _timer.expires_from_now(boost::posix_time::seconds(3));
    try {
        switch (buffer[0]) {
            case 0x05:
                _interest_callback(shared_from_this(), ndn::Interest(ndn::Block((uint8_t *) buffer, size)));
                break;
            case 0x06:
                _data_callback(shared_from_this(), ndn::Data(ndn::Block((uint8_t *) buffer, size)));
                break;
            default:
                break;
        }
    } catch (const std::exception &e) {
        std::cerr << e.what() << std::endl;
    }
}

void UdpMasterFace::UdpSubFace::timerHandler(const boost::system::error_code &err, bool last_chance) {
    if (_timer.expires_at() <= boost::asio::deadline_timer::traits_type::now()) {
        if (!last_chance) {
            // endpoint must manifest itself in the given time, else the socket will close (icmp or timeout)
            _master_face._strand.post(boost::bind(&UdpMasterFace::sendImpl, _master_face.shared_from_this(), "0", _endpoint));
            _timer.expires_from_now(boost::posix_time::seconds(2));
            _timer.async_wait(boost::bind(&UdpSubFace::timerHandler, shared_from_this(), _1, true));
        } else {
            std::stringstream ss;
            ss << "no activity from/to " << _endpoint << " since 5s" << std::endl;
            logger::log(logger::INFO, ss.str());
            _error_callback(shared_from_this());
        }
    } else {
        _timer.async_wait(boost::bind(&UdpSubFace::timerHandler, shared_from_this(), _1, false));
    }
}

//----------------------------------------------------------------------------------------------------------------------

UdpMasterFace::UdpMasterFace(boost::asio::io_service &ios, size_t max_connection, uint16_t port)
        : MasterFace(ios, max_connection)
        , _local_endpoint(boost::asio::ip::udp::v4(), port)
        , _socket(_ios, boost::asio::ip::udp::endpoint(boost::asio::ip::udp::v4(), port))
        , _strand(_ios) {

}

std::string UdpMasterFace::getUnderlyingProtocol() const {
    return "UDP";
}

void UdpMasterFace::listen(const MasterFace::NotificationCallback &notification_callback, const Face::InterestCallback &interest_callback,
                           const Face::DataCallback &data_callback, const MasterFace::ErrorCallback &error_callback) {
    _notification_callback = notification_callback;
    _interest_callback = interest_callback;
    _data_callback = data_callback;
    _error_callback = error_callback;
    std::stringstream ss;
    ss << "master face with ID = " << _master_face_id << " listening on udp://" << _local_endpoint;
    logger::log(logger::INFO, ss.str());
    read();
}

void UdpMasterFace::close() {
    _socket.close();
    for(const auto &face : _faces) {
        face.second->close();
    }
}

void UdpMasterFace::sendToAllFaces(const std::string &message) {
    for(const auto &face : _faces) {
        face.second->send(message);
    }
}

void UdpMasterFace::sendToAllFaces(const ndn::Interest &interest) {
    std::string message((const char *)interest.wireEncode().wire(), interest.wireEncode().size());
    for(const auto &face : _faces) {
        face.second->send(message);
    }
}

void UdpMasterFace::sendToAllFaces(const ndn::Data &data) {
    std::string message((const char *)data.wireEncode().wire(), data.wireEncode().size());
    for(const auto &face : _faces) {
        face.second->send(message);
    }
}

void UdpMasterFace::read() {
    _socket.async_receive_from(boost::asio::buffer(_buffer, BUFFER_SIZE), _remote_endpoint,
                               boost::bind(&UdpMasterFace::readHandler, shared_from_this(), _1, _2));
}

void UdpMasterFace::readHandler(const boost::system::error_code &err, size_t bytes_transferred) {
    if(!err) {
        std::shared_ptr<UdpSubFace> face;
        auto it = _faces.find(_remote_endpoint);
        if (it != _faces.end()) {
            face = it->second;
            face->proceedPacket(_buffer, bytes_transferred);
        } else if (_faces.size() < _max_connection) {
            std::stringstream ss;
            ss << "new connection from udp://" << _remote_endpoint;
            logger::log(logger::INFO, ss.str());
            face = std::make_shared<UdpSubFace>(*this, _remote_endpoint);
            face->open(_interest_callback, _data_callback, boost::bind(&UdpMasterFace::onFaceError, shared_from_this(), _1));
            _notification_callback(shared_from_this(), face);
            _faces.emplace(_remote_endpoint, face);
            face->proceedPacket(_buffer, bytes_transferred);
        }
        read();
    } else {
        std::cerr << "[ERROR] " << err.message() << std::endl;
    }
}

void UdpMasterFace::sendImpl(const std::string &message, const boost::asio::ip::udp::endpoint &endpoint) {
    _queue.emplace_back(message, endpoint);
    if (_queue.size() == 1) {
        write();
    }
}

void UdpMasterFace::write() {
    auto &message = _queue.front();
    _socket.async_send_to(boost::asio::buffer(message.first), message.second,
                          _strand.wrap(boost::bind(&UdpMasterFace::writeHandler, shared_from_this(), _1, _2)));
}

void UdpMasterFace::writeHandler(const boost::system::error_code &err, size_t bytesTransferred) {
    if(!err) {
        _queue.pop_front();
        if (!_queue.empty()) {
            write();
        }
    } else {
        std::cerr << err.message() << std::endl;
    }
}

void UdpMasterFace::onFaceError(const std::shared_ptr<Face> &face) {
    _faces.erase(((UdpSubFace*)face.get())->getEndpoint());
    _error_callback(shared_from_this(), face);
}


