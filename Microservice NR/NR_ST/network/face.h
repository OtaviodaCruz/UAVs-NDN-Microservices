#pragma once

#include <ndn-cxx/interest.hpp>
#include <ndn-cxx/data.hpp>

#include <boost/asio.hpp>
//#include <boost/function.hpp>

#include <functional>

#include <memory>
#include <string>

class Face {
public:
    using InterestCallback = std::function<void(const std::shared_ptr<Face>&, const ndn::Interest&)>;
    using DataCallback = std::function<void(const std::shared_ptr<Face>&, const ndn::Data&)>;
    using ErrorCallback = std::function<void(const std::shared_ptr<Face>&)>;

private:
    static size_t counter;

protected:
    const size_t _face_id;

    bool _is_connected = false;

    boost::asio::io_service &_ios;

    InterestCallback _interest_callback;
    DataCallback _data_callback;
    ErrorCallback _error_callback;

public:
    explicit Face(boost::asio::io_service &ios) : _face_id(++counter), _ios(ios) {

    };

    virtual ~Face() = default;

    size_t getFaceId() const {
        return _face_id;
    }

    bool isConnected() {
        return _is_connected;
    }

    virtual std::string getUnderlyingProtocol() const = 0;

    virtual std::string getUnderlyingEndpoint() const = 0;

    virtual void open(const InterestCallback &interest_callback, const DataCallback &data_callback, const ErrorCallback &error_callback) = 0;

    virtual void close() = 0;

    virtual void send(const std::string &message) = 0;

    virtual void send(const ndn::Interest &interest) = 0;

    virtual void send(const ndn::Data &data) = 0;
};