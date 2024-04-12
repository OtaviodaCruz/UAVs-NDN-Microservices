#pragma once

#include <ndn-cxx/interest.hpp>
#include <ndn-cxx/data.hpp>

#include <boost/asio.hpp>

#include <memory>
#include <unordered_map>
#include <unordered_set>
#include <functional>

#include "rapidjson/document.h"

#include "module.h"
#include "network/face.h"
#include "network/master_face.h"
#include "fib.h"

class NamedRouter : public Module {
    const std::string _name;

    Fib _fib;

    char _command_buffer[65536];
    boost::asio::ip::udp::socket _command_socket;
    boost::asio::ip::udp::endpoint _remote_command_endpoint;

    size_t _request_id = 1;
    std::map<size_t, std::function<void(bool)>> _requests;
    std::map<size_t, std::shared_ptr<boost::asio::deadline_timer>> _request_timers;
    boost::asio::ip::udp::endpoint _manager_endpoint;

    std::unordered_map<size_t, std::shared_ptr<Face>> _egress_faces;
    std::shared_ptr<MasterFace> _tcp_consumer_master_face;
    std::shared_ptr<MasterFace> _tcp_producer_master_face;
    std::shared_ptr<MasterFace> _udp_consumer_master_face;
    std::shared_ptr<MasterFace> _udp_producer_master_face;

public:
    NamedRouter(const std::string &name, uint16_t local_consumer_port, uint16_t local_producer_port, uint16_t local_command_port);

    ~NamedRouter() override = default;

    void run() override;

    void onConsumerInterest(const std::shared_ptr<Face> &consumer_face, const ndn::Interest &interest);

    void onConsumerData(const std::shared_ptr<Face> &consumer_face, const ndn::Data &data);

    void onProducerInterest(const std::shared_ptr<Face> &producer_face, const ndn::Interest &interest);

    void onManagerValidation(const std::shared_ptr<Face> &producer_face, const ndn::Interest &interest, const ndn::Name &prefix, bool result);

    void onTimeout(const boost::system::error_code &err, size_t index);

    void onProducerData(const std::shared_ptr<Face> &producer_face, const ndn::Data &data);

    void onMasterFaceNotification(const std::shared_ptr<MasterFace> &master_face, const std::shared_ptr<Face> &face);

    void onMasterFaceError(const std::shared_ptr<MasterFace> &master_face, const std::shared_ptr<Face> &face);

    void onFaceError(const std::shared_ptr<Face> &face);

    void commandRead();

    void commandReadHandler(const boost::system::error_code &err, size_t bytes_transferred);

    void commandReply(const rapidjson::Document &document);

    void commandEditConfig(const rapidjson::Document &document);

    void commandAddFace(const rapidjson::Document &document);

    void commandDelFace(const rapidjson::Document &document);

    void commandAddRoute(const rapidjson::Document &document);

    void commandDelRoute(const rapidjson::Document &document);

    void commandList(const rapidjson::Document &document);
    
    void commandReportErrorFace(const std::shared_ptr<Face> &face);
};
