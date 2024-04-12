#pragma once

#include <memory>
#include <atomic>

#include "face.h"

class MasterFace {
public:
    using NotificationCallback = std::function<void(const std::shared_ptr<MasterFace> &master_face, const std::shared_ptr<Face>&)>;
    using ErrorCallback = std::function<void(const std::shared_ptr<MasterFace> &master_face, const std::shared_ptr<Face>&)>;

private:
    static size_t counter;

protected:
    const size_t _master_face_id;

    boost::asio::io_service &_ios;

    size_t _max_connection;

    NotificationCallback _notification_callback;
    Face::InterestCallback _interest_callback;
    Face::DataCallback _data_callback;
    ErrorCallback _error_callback;

public:
    MasterFace(boost::asio::io_service &ios, size_t max_connection) : _master_face_id(++counter), _ios(ios), _max_connection(max_connection) {

    }

    virtual ~MasterFace() = default;

    boost::asio::io_service& get_io_service() const {
        return _ios;
    }

    size_t getMasterFaceId() const {
        return _master_face_id;
    }

    virtual std::string getUnderlyingProtocol() const = 0;

    virtual void listen(const NotificationCallback &notification_callback, const Face::InterestCallback &interest_callback,
                        const Face::DataCallback &data_callback, const ErrorCallback &error_callback) = 0;

    virtual void close() = 0;

    virtual void sendToAllFaces(const std::string &message) = 0;

    virtual void sendToAllFaces(const ndn::Interest &interest) = 0;

    virtual void sendToAllFaces(const ndn::Data &data) = 0;
};