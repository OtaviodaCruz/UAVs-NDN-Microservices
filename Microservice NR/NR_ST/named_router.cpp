#include "named_router.h"

#include "ndn-cxx/security/key-chain.hpp"

#include <boost/bind.hpp>

#include "network/tcp_master_face.h"
#include "network/tcp_face.h"
#include "network/udp_master_face.h"
#include "network/udp_face.h"
#include "log/logger.h"

NamedRouter::NamedRouter(const std::string &name, uint16_t local_consumer_port, uint16_t local_producer_port, uint16_t local_command_port)
        : Module(1)
        , _name(name)
        , _command_socket(_ios, {{}, local_command_port}) {
    _tcp_consumer_master_face = std::make_shared<TcpMasterFace>(_ios, 16, local_consumer_port);
    _udp_consumer_master_face = std::make_shared<UdpMasterFace>(_ios, 16, local_consumer_port);
    _tcp_producer_master_face = std::make_shared<TcpMasterFace>(_ios, 16, local_producer_port);
    _udp_producer_master_face = std::make_shared<UdpMasterFace>(_ios, 16, local_producer_port);
}

void NamedRouter::run() {
    commandRead();
    _tcp_consumer_master_face->listen(boost::bind(&NamedRouter::onMasterFaceNotification, this, _1, _2),
                                      boost::bind(&NamedRouter::onConsumerInterest, this, _1, _2),
                                      boost::bind(&NamedRouter::onConsumerData, this, _1, _2),
                                      boost::bind(&NamedRouter::onMasterFaceError, this, _1, _2));
    _udp_consumer_master_face->listen(boost::bind(&NamedRouter::onMasterFaceNotification, this, _1, _2),
                                      boost::bind(&NamedRouter::onConsumerInterest, this, _1, _2),
                                      boost::bind(&NamedRouter::onConsumerData, this, _1, _2),
                                      boost::bind(&NamedRouter::onMasterFaceError, this, _1, _2));
    _tcp_producer_master_face->listen(boost::bind(&NamedRouter::onMasterFaceNotification, this, _1, _2),
                                      boost::bind(&NamedRouter::onProducerInterest, this, _1, _2),
                                      boost::bind(&NamedRouter::onProducerData, this, _1, _2),
                                      boost::bind(&NamedRouter::onMasterFaceError, this, _1, _2));
    _udp_producer_master_face->listen(boost::bind(&NamedRouter::onMasterFaceNotification, this, _1, _2),
                                      boost::bind(&NamedRouter::onProducerInterest, this, _1, _2),
                                      boost::bind(&NamedRouter::onProducerData, this, _1, _2),
                                      boost::bind(&NamedRouter::onMasterFaceError, this, _1, _2));
}

void NamedRouter::onConsumerInterest(const std::shared_ptr<Face> &consumer_face, const ndn::Interest &interest) {
    
    std::stringstream ss;
    ss << "onConsumerInterest" << interest.getName();
    logger::log(logger::INFO, ss.str());

    auto producer_faces = _fib.get(interest.getName());
    for (const auto& producer_face : producer_faces) {
        producer_face->send(interest);
    }
}

void NamedRouter::onConsumerData(const std::shared_ptr<Face> &consumer_face, const ndn::Data &data) {
    // drop

    std::stringstream ss;
    ss << "onConsumerData" << data.getName();
    logger::log(logger::INFO, ss.str());
    
    commandReportErrorFace(consumer_face);
}

void NamedRouter::commandReportErrorFace(const std::shared_ptr<Face> &face) {
    logger::log(logger::INFO, "[Face Error] Package droped");
    try {
        if (_manager_endpoint.address() != boost::asio::ip::address_v4::any() && _manager_endpoint.port() != 0){ 
            size_t faceID = face->getFaceId();

            std::stringstream ss;        
            ss << R"({"name":")" << _name << R"(", "type":"report", "action":"face_error", "face_id":)" << faceID << "}";

            _command_socket.send_to(boost::asio::buffer(ss.str()), _manager_endpoint);
        }
    }
    catch (...) {
        logger::log(logger::INFO, "[catch] Error on running commandReportErrorFace");
    }
}

void NamedRouter::onProducerInterest(const std::shared_ptr<Face> &producer_face, const ndn::Interest &interest) {
    
    //std::stringstream ss;
    //ss << "onProducerInterest " << interest.getName();
    //logger::log(logger::INFO, ss.str());
    
    static const ndn::Name localhost("/localhost");
    static const ndn::Name localhop("/localhop");
    if (localhost.isPrefixOf(interest.getName()) || localhop.isPrefixOf(interest.getName())) {
        std::string s((const char *)interest.getName().get(4).wire(), interest.getName().get(4).size());
        while(s[0] != 0x07){
            switch((uint8_t)s[1]){
                case 0xFF:
                    s.erase(0, 10);
                    break;
                case 0xFE:
                    s.erase(0, 6);
                    break;
                case 0xFD:
                    s.erase(0, 4);
                    break;
                default:
                    s.erase(0, 2);
                    break;
            }
        }
        ndn::Name prefix(ndn::Block((uint8_t*)s.c_str(), s.size()));
        std::stringstream ss;
        ss << "face with ID = " << producer_face->getFaceId() << " want to register " << prefix << " name prefix";
        logger::log(logger::INFO, ss.str());
        if(_manager_endpoint != boost::asio::ip::udp::endpoint()) {
            ss = std::stringstream();
            ss << R"({"name":")" << _name << R"(", "type":"request", "id":)" << _request_id << R"(, "action":"route_registration", "face_id":)"
               << producer_face->getFaceId() << R"(, "prefix":")" << prefix << "\"}";
            _requests.emplace(_request_id, boost::bind(&NamedRouter::onManagerValidation, this, producer_face, interest, prefix, _1));
            auto timer = std::make_shared<boost::asio::deadline_timer>(_ios);
            timer->expires_from_now(boost::posix_time::seconds(20));
            timer->async_wait(boost::bind(&NamedRouter::onTimeout, this, _1, _request_id));
            _request_timers.emplace(_request_id, timer);
            ++_request_id;
            _command_socket.send_to(boost::asio::buffer(ss.str()), _manager_endpoint);
        } else {
            ss = std::stringstream();
            ss << "no manager endpoint";
            logger::log(logger::ERROR, ss.str());
        }
    }
}

void NamedRouter::onManagerValidation(const std::shared_ptr<Face> &producer_face, const ndn::Interest &interest, const ndn::Name &prefix, bool result) {
    if (result) {
        std::stringstream ss;
        ss << prefix << " name prefix accepted by manager for face with ID = " << producer_face->getFaceId();
        logger::log(logger::INFO, ss.str());
        ndn::Data data(interest.getName());
        uint8_t content[44] = {0x65, 0x2a, 0x66, 0x01, 0xc8, 0x67, 0x07, 0x53, 0x75, 0x63, 0x63, 0x65, 0x73, 0x73, 0x68, 0x1c, 0x07, 0x0d, 0x08, 0x03, 0x63, 0x6f, 0x6d, 0x08, 0x06, 0x67, 0x6f, 0x6f, 0x67, 0x6c, 0x65, 0x69, 0x02, 0x01, 0x0d, 0x6f, 0x01, 0x00, 0x6a, 0x01, 0x00, 0x6c, 0x01, 0x01};
        data.setContent(content, 44);
        data.setFreshnessPeriod(boost::chrono::milliseconds(0));
        ndn::KeyChain k;
        k.sign(data);
        producer_face->send(data);
        _fib.insert(producer_face, prefix);
    } else {
        std::stringstream ss;
        ss << prefix << " name prefix refused by manager for face with ID = " << producer_face->getFaceId();
        logger::log(logger::INFO, ss.str());
    }
}

void NamedRouter::onTimeout(const boost::system::error_code &err, size_t index) {
    if (!err) {
        _requests.erase(index);
        _request_timers.erase(index);
    }
}

void NamedRouter::onProducerData(const std::shared_ptr<Face> &producer_face, const ndn::Data &data) {

    std::stringstream ss;
    ss << "onProducerData" <<  data.getName();
    logger::log(logger::INFO, ss.str());

    if (_fib.isPrefix(producer_face, data.getName())) {
        _tcp_consumer_master_face->sendToAllFaces(data);
        _udp_consumer_master_face->sendToAllFaces(data);
    }
}

void NamedRouter::onMasterFaceNotification(const std::shared_ptr<MasterFace> &master_face, const std::shared_ptr<Face> &face) {
    std::stringstream ss;
    ss << "new face with ID = " << face->getFaceId() << " form master face with ID = " << master_face->getMasterFaceId();
    logger::log(logger::INFO, ss.str());
}

void NamedRouter::onMasterFaceError(const std::shared_ptr<MasterFace> &master_face, const std::shared_ptr<Face> &face) {
    std::stringstream ss;
    ss << "face with ID = " << face->getFaceId() << " from master face with ID = " << master_face->getMasterFaceId() << " can't process normally";
    logger::log(logger::ERROR, ss.str());
    std::stringstream ss1;
    ss1 << R"({"name":")" << _name << R"(", "type":"report", "action":"producer_disconnection", "face_id":)" << face->getFaceId() << "}";
    _command_socket.send_to(boost::asio::buffer(ss1.str()), _remote_command_endpoint);
}

void NamedRouter::onFaceError(const std::shared_ptr<Face> &face) {
    //_fib.remove(face);
    _egress_faces.erase(face->getFaceId());
    std::stringstream ss;
    ss << "face with ID = " << face->getFaceId() << " can't process normally";
    logger::log(logger::ERROR, ss.str());
}

void NamedRouter::commandRead() {
    _command_socket.async_receive_from(boost::asio::buffer(_command_buffer, 65536), _remote_command_endpoint,
                                       boost::bind(&NamedRouter::commandReadHandler, this, _1, _2));
}

void NamedRouter::commandReadHandler(const boost::system::error_code &err, size_t bytes_transferred) {
    enum action_type {
        REPLY,
        EDIT_CONFIG,
        ADD_FACE,
        DEL_FACE,
        ADD_ROUTE,
        DEL_ROUTE,
        LIST
    };

    static const std::map<std::string, action_type> ACTIONS = {
            {"reply", REPLY},
            {"edit_config", EDIT_CONFIG},
            {"add_face", ADD_FACE},
            {"del_face", DEL_FACE},
            {"add_route", ADD_ROUTE},
            {"del_route", DEL_ROUTE},
            {"list", LIST}
    };

    if(!err) {
        try {
            rapidjson::Document document;
            document.Parse(_command_buffer, bytes_transferred);
            if(!document.HasParseError()){
                if(document.HasMember("action") && document["action"].IsString() && document.HasMember("id") && document["id"].IsUint()){
                    auto it = ACTIONS.find(document["action"].GetString());
                    if(it != ACTIONS.end()) {
                        switch (it->second) {
                            case REPLY:
                                commandReply(document);
                                break;
                            case EDIT_CONFIG:
                                commandEditConfig(document);
                                break;
                            case ADD_FACE:
                                commandAddFace(document);
                                break;
                            case DEL_FACE:
                                commandDelFace(document);
                                break;
                            case ADD_ROUTE:
                                commandAddRoute(document);
                                break;
                            case DEL_ROUTE:
                                commandDelRoute(document);
                                break;
                            case LIST:
                                commandList(document);
                        }
                    }
                } else{
                    //std::string response = R"({"status":"fail", "reason":"action not provided or not implemented"})";
                    //_command_socket.send_to(boost::asio::buffer(response), _remote_command_endpoint);
                }
            } else {
                //std::string error_extract(&_command_buffer[document.GetErrorOffset()], std::min(32ul, bytes_transferred - document.GetErrorOffset()));
                //std::string response = R"({"status":"fail", "reason":"error while parsing"})";
                //_command_socket.send_to(boost::asio::buffer(response), _remote_command_endpoint);
            }
        } catch(const std::exception &e) {
            std::cout << e.what() << std::endl;
        }
        commandRead();
    } else {
        std::cerr << "command socket error !" << std::endl;
    }
}

void NamedRouter::commandReply(const rapidjson::Document &document) {
    if (document.HasMember("result") && document["result"].IsBool()) {
        auto it = _requests.find(document["id"].GetUint());
        if (it != _requests.end()) {
            it->second(document["result"].GetBool());
        }
    }
}

void NamedRouter::commandEditConfig(const rapidjson::Document &document) {
    std::vector<std::string> changes;
    if (document.HasMember("manager_address") && document.HasMember("manager_port") && document["manager_address"].IsString() && document["manager_port"].IsUint()) {
        bool has_change = false;
        boost::asio::ip::udp::endpoint new_endpoint(boost::asio::ip::address::from_string(document["manager_address"].GetString()), document["manager_port"].GetUint());
        if (new_endpoint != _manager_endpoint) {
            _manager_endpoint = new_endpoint;
            has_change = true;
        }
        if (has_change) {
            changes.emplace_back("manager_endpoint");
        }
    }

    std::stringstream ss;
    ss << R"({"name":")" << _name << R"(", "type":"reply", "id":)" << document["id"].GetUint() << R"(, "action":"edit_config", "changes":[)";
    bool first = true;
    for(const auto& change : changes) {
        if (first) {
            first = false;
        } else {
            ss << ",";
        }
        ss << '"' << change << '"';
    }
    ss << "]}";
    _command_socket.send_to(boost::asio::buffer(ss.str()), _remote_command_endpoint);
}

void NamedRouter::commandAddFace(const rapidjson::Document &document) {
    enum layer_type {
        TCP,
        UDP,
    };

    static const std::unordered_map<std::string, layer_type> LAYERS = {
            {"tcp", TCP},
            {"udp", UDP},
    };

    if (document.HasMember("layer") && document.HasMember("address") && document.HasMember("port")
        && document["layer"].IsString() && document["address"].IsString() && document["port"].IsUint()) {
        auto it = LAYERS.find(document["layer"].GetString());
        if (it != LAYERS.end()) {
            std::shared_ptr<Face> face;
            switch (it->second) {
                case TCP:
                    face = std::make_shared<TcpFace>(_ios, document["address"].GetString(), document["port"].GetUint());
                    break;
                case UDP:
                    face = std::make_shared<UdpFace>(_ios, document["address"].GetString(), document["port"].GetUint());
                    break;
            }
            face->open(boost::bind(&NamedRouter::onProducerInterest, this, _1, _2),
                       boost::bind(&NamedRouter::onProducerData, this, _1, _2),
                       boost::bind(&NamedRouter::onFaceError, this, _1));
            _egress_faces.emplace(face->getFaceId(), face);
            std::stringstream ss;
            ss << R"({"name":")" << _name << R"(", "type":"reply", "id":)" << document["id"].GetUint() << R"(, "action":"add_face", "face_id":)" << face->getFaceId() << "}";
            _command_socket.send_to(boost::asio::buffer(ss.str()), _remote_command_endpoint);
        }
    }
}

void NamedRouter::commandDelFace(const rapidjson::Document &document) {
    if (document.HasMember("face_id") && document["face_id"].IsUint()) {
        size_t face_id = document["face_id"].GetUint();
        bool ok = _egress_faces.erase(face_id);
        std::stringstream ss;
        ss << R"({"name":")" << _name << R"(", "type":"reply", "id":)" << document["id"].GetUint() << R"(", action":"del_face", "face_id":)" << face_id << R"(, "status":)" << ok << "}";
        _command_socket.send_to(boost::asio::buffer(ss.str()), _remote_command_endpoint);
    }
}

void NamedRouter::commandAddRoute(const rapidjson::Document &document) {
    if (document.HasMember("face_id") && document["face_id"].IsUint() && document.HasMember("prefixes") && document["prefixes"].IsArray()) {
        std::stringstream ss;
        ss << R"({"name":")" << _name << R"(", "type":"reply", "id":)" << document["id"].GetUint() << R"(, "action":"add_route", )";
        auto&& prefixes = document["prefixes"].GetArray();
        if (prefixes.Empty()) {
            ss << R"("status":"fail", "reason":"empty prefix list"})";
        } else {
            auto it = _egress_faces.find(document["face_id"].GetUint());
            if (it != _egress_faces.end()) {
                for (auto &prefix : prefixes) {
                    if (prefix.IsString()) {
                        ndn::Name name_prefix(prefix.GetString());
                        _fib.insert(it->second, name_prefix);
                        std::stringstream ss1;
                        ss1 << name_prefix << " name added by manager for face with ID = " << it->second->getFaceId();
                        logger::log(logger::INFO, ss1.str());
                    }
                }
                ss << R"("status":"success"})";
            } else {
                ss << R"("status":"fail", "reason":"unknown face id"})";
            }
        }
        _command_socket.send_to(boost::asio::buffer(ss.str()), _remote_command_endpoint);
    }
}

void NamedRouter::commandDelRoute(const rapidjson::Document &document) {
    if (document.HasMember("face_id") && document["face_id"].IsUint() && document.HasMember("prefixes") && document["prefixes"].IsArray()) {
        std::stringstream ss;
        ss << R"({"name":")" << _name << R"(", "type":"reply", "id":)" << document["id"].GetUint() << R"(, "action":"del_route", )";
        auto&& prefixes = document["prefixes"].GetArray();
        if (prefixes.Empty()) {
            ss << R"("status":"fail", "reason":"empty prefix list"})";
        } else {
            auto it = _egress_faces.find(document["face_id"].GetUint());
            if (it != _egress_faces.end()) {
                for (auto &prefix : prefixes) {
                    if (prefix.IsString()) {
                        ndn::Name name_prefix(prefix.GetString());
                        _fib.remove(it->second, name_prefix);
                        std::stringstream ss1;
                        ss1 << name_prefix << " name removed by manager for face with ID = " << it->second->getFaceId();
                        logger::log(logger::INFO, ss1.str());
                    }
                }
                ss << R"("status":"success"})";
            } else {
                ss << R"("status":"fail", "reason":"unknown face id"})";
            }
        }
        _command_socket.send_to(boost::asio::buffer(ss.str()), _remote_command_endpoint);
    }
}


void NamedRouter::commandList(const rapidjson::Document &document) {
    std::stringstream ss;
    ss << R"({"name":")" << _name << R"(", "type":"reply", "id":)" << document["id"].GetUint() << R"(, "action":"list", "table":{"type":"fib", "tree":)" << _fib.toJSON() << "}}";
    _command_socket.send_to(boost::asio::buffer(ss.str()), _remote_command_endpoint);
}
