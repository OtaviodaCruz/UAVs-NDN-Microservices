#include "master_face.h"

#include <boost/asio.hpp>

#include <unordered_set>

#include "tcp_face.h"

class TcpMasterFace : public MasterFace, public std::enable_shared_from_this<TcpMasterFace> {
private:
    uint16_t _port;
    boost::asio::ip::tcp::socket _socket;
    boost::asio::ip::tcp::acceptor _acceptor;
    std::unordered_set<std::shared_ptr<Face>> _faces;

public:
    TcpMasterFace(boost::asio::io_service &ios, size_t max_connection, uint16_t port);

    ~TcpMasterFace() override = default;

    std::string getUnderlyingProtocol() const override;

    void listen(const NotificationCallback &notification_callback, const Face::InterestCallback &interest_callback,
                const Face::DataCallback &data_callback, const ErrorCallback &error_callback) override;

    void close() override;

    void sendToAllFaces(const std::string &message) override;

    void sendToAllFaces(const ndn::Interest &interest) override;

    void sendToAllFaces(const ndn::Data &data) override;

private:
    void accept();

    void acceptHandler(const boost::system::error_code &err);

    void onFaceError(const std::shared_ptr<Face> &face);
};