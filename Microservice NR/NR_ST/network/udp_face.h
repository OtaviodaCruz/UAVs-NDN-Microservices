#pragma once

#include "face.h"

#include <boost/asio.hpp>

#include <iostream>
#include <string>
#include <deque>
#include <vector>


class UdpFace : public Face, public std::enable_shared_from_this<UdpFace> {
public:
    static const size_t BUFFER_SIZE = 1 << 16;

private:
    boost::asio::ip::udp::endpoint _endpoint;
    boost::asio::ip::udp::endpoint _remote_endpoint;
    boost::asio::ip::udp::socket _socket;
    boost::asio::strand _strand;
    char _buffer[BUFFER_SIZE];
    std::deque<std::string> _queue;

    boost::asio::deadline_timer _timer;

public:
    // use these when creating a face yourself
    UdpFace(boost::asio::io_service &ios, const std::string &host, uint16_t port);

    UdpFace(boost::asio::io_service &ios, const boost::asio::ip::udp::endpoint &endpoint);

    ~UdpFace() override = default;

    std::string getUnderlyingProtocol() const override;

    std::string getUnderlyingEndpoint() const override;

    void open(const InterestCallback &interest_callback, const DataCallback &data_callback, const ErrorCallback &error_callback) override;

    void close() override;

    void send(const std::string &message) override;

    void send(const ndn::Interest &interest) override;

    void send(const ndn::Data &data) override;

private:
    void read();

    void readHandler(const boost::system::error_code &err, size_t bytes_transferred);

    void sendImpl(const std::string &message);

    void write();

    void writeHandler(const boost::system::error_code &err, size_t bytesTransferred);
};