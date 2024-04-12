#include "tcp_master_face.h"

#include <boost/bind.hpp>

#include "../log/logger.h"

TcpMasterFace::TcpMasterFace(boost::asio::io_service &ios, size_t max_connection, uint16_t port)
        : MasterFace(ios, max_connection)
        , _port(port)
        , _socket(ios)
        , _acceptor(ios, boost::asio::ip::tcp::endpoint(boost::asio::ip::tcp::v4(), port)) {

}

std::string TcpMasterFace::getUnderlyingProtocol() const {
    return "TCP";
}

void TcpMasterFace::listen(const NotificationCallback &notification_callback, const Face::InterestCallback &interest_callback,
                           const Face::DataCallback &data_callback, const ErrorCallback &error_callback) {
    _notification_callback = notification_callback;
    _interest_callback = interest_callback;
    _data_callback = data_callback;
    _error_callback = error_callback;
    _acceptor.listen(16);
    std::stringstream ss;
    ss << "master face with ID = " << _master_face_id << " listening on tcp://0.0.0.0:" << _port;
    logger::log(logger::INFO, ss.str());
    accept();
}

void TcpMasterFace::close() {
    _socket.close();
    for(const auto &face : _faces) {
        face->close();
    }
}

void TcpMasterFace::sendToAllFaces(const std::string &message) {
    for(const auto &face : _faces) {
        face->send(message);
    }
}

void TcpMasterFace::sendToAllFaces(const ndn::Interest &interest) {
    std::string message((const char *)interest.wireEncode().wire(), interest.wireEncode().size());
    for(const auto &face : _faces) {
        face->send(message);
    }
}

void TcpMasterFace::sendToAllFaces(const ndn::Data &data) {
    std::string message((const char *)data.wireEncode().wire(), data.wireEncode().size());
    for(const auto &face : _faces) {
        face->send(message);
    }
}

void TcpMasterFace::accept() {
    _acceptor.async_accept(_socket, boost::bind(&TcpMasterFace::acceptHandler, shared_from_this(), _1));
}

void TcpMasterFace::acceptHandler(const boost::system::error_code &err) {
    if(!err) {
        if(_faces.size() < _max_connection) {
            std::stringstream ss;
            ss << "new connection from tcp://" << _socket.remote_endpoint();
            logger::log(logger::INFO, ss.str());
            auto face = std::make_shared<TcpFace>(std::move(_socket));
            _faces.emplace(face);
            _notification_callback(shared_from_this(), face);
            face->open(_interest_callback, _data_callback, boost::bind(&TcpMasterFace::onFaceError, shared_from_this(), _1));
        }
        accept();
    } else {
        std::cerr << err.message() << std::endl;
    }
}

void TcpMasterFace::onFaceError(const std::shared_ptr<Face> &face) {
    _faces.erase(face);
    _error_callback(shared_from_this(), face);
}