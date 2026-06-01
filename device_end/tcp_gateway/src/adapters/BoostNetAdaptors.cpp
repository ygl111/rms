#include "dpower/net/Interfaces.h"
#include <string>
#include <boost/asio.hpp>
#include <memory>
#include <utility>
#include "logic/utils/Logger.h"

namespace DPower {
namespace Net {

// ---------------------------------------------
// BoostErrorCode
// ---------------------------------------------
class BoostErrorCode : public DPowerErrorCode {
public:
    explicit BoostErrorCode(const boost::system::error_code& ec) : ec_(ec) {}
    int         Value()   const override { return ec_.value(); }
    std::string Message() const override { return ec_.message(); }
    explicit operator bool() const override { return static_cast<bool>(ec_); }
private:
    boost::system::error_code ec_;
};

// ---------------------------------------------
// BoostIOContext
// ---------------------------------------------
class BoostIOContext : public DPowerIOContext {
public:
    BoostIOContext() = default;
    void Run()  override { io_.run(); }
    void Stop() override { io_.stop(); }
    void Post(std::function<void()> f) override {
        boost::asio::post(io_, std::move(f));
    }

    boost::asio::io_context& Raw() { return io_; }
private:
    boost::asio::io_context io_;
};

// ---------------------------------------------
// BoostTCPEndpoint
// ---------------------------------------------
class BoostTCPEndpoint : public DPowerTCPEndpoint {
public:
    BoostTCPEndpoint(const std::string& addr, uint16_t port)
        : endpoint_(boost::asio::ip::make_address(addr), port) {}

    std::string Address() const override { return endpoint_.address().to_string(); }
    uint16_t    Port()    const override { return endpoint_.port(); }

    const boost::asio::ip::tcp::endpoint& Raw() const { return endpoint_; }
private:
    boost::asio::ip::tcp::endpoint endpoint_;
};


// ---------------------------------------------
// BoostTCPSocket
// ---------------------------------------------
class BoostTCPSocket : public DPowerTCPSocket {
public:
    explicit BoostTCPSocket(boost::asio::ip::tcp::socket socket)
        : socket_(std::move(socket)) {}

    std::string SafeRemoteAddress() const {
        boost::system::error_code ec;
        auto ep = socket_.remote_endpoint(ec);
        if (ec) {
            return "";
        }
        auto addr = ep.address().to_string(ec);
        if (ec) {
            return "";
        }
        return addr;
    }

    uint16_t SafeRemotePort() const {
        boost::system::error_code ec;
        auto ep = socket_.remote_endpoint(ec);
        if (ec) {
            return 0;
        }
        return ep.port();
    }

    std::string SafeRemoteDesc() const {
        auto addr = SafeRemoteAddress();
        auto port = SafeRemotePort();
        if (addr.empty() && port == 0) {
            return "<disconnected>";
        }
        return addr + ":" + std::to_string(port);
    }

    void AsyncReadSome(MutableBuffer buffer, ReadHandler handler) override {
        socket_.async_read_some(
            boost::asio::mutable_buffer(buffer.data, buffer.size),
            [h = std::move(handler)](const boost::system::error_code& ec, std::size_t bytes) mutable {
                h(BoostErrorCode(ec), bytes);
            });
    }

    void AsyncWrite(const void* data, std::size_t len, WriteHandler handler) override {
        auto buf = boost::asio::const_buffer(data, len);
        boost::asio::async_write(socket_, buf,
            [h = std::move(handler)](const boost::system::error_code& ec, std::size_t bytes) mutable {
                h(BoostErrorCode(ec), bytes);
            });
    }

    std::string RemoteAddress() const override {
        return SafeRemoteAddress();
    }
    uint16_t RemotePort() const override {
        return SafeRemotePort();
    }

    void Close() override {
        boost::system::error_code ec;
        socket_.close(ec);
    }
    
    void set_no_delay(bool enable) {
        boost::system::error_code ec;
        socket_.set_option(boost::asio::ip::tcp::no_delay(enable), ec);
        auto remote_desc = SafeRemoteDesc();
        if (ec) {
            Utils::Logger::Instance().Log(
                "WARN",
                "Failed to set TCP_NODELAY for " + remote_desc + ": " + ec.message(),
                "BoostNet");
        } else {
            Utils::Logger::Instance().Log(
                "INFO",
                std::string("TCP_NODELAY ") + (enable ? "enabled" : "disabled") +
                    " for socket " + remote_desc,
                "BoostNet");
        }
    }

    boost::asio::ip::tcp::socket& Raw() { return socket_; }
private:
    boost::asio::ip::tcp::socket socket_;
};


// ---------------------------------------------
// BoostTCPAcceptor
// ---------------------------------------------
class BoostTCPAcceptor : public DPowerTCPAcceptor {
public:
    BoostTCPAcceptor(boost::asio::io_context& io, const boost::asio::ip::tcp::endpoint& ep)
        : acceptor_(io, ep) {}

    void AsyncAccept(AcceptHandler handler) override {
        acceptor_.async_accept([
            h = std::move(handler)
        ](const boost::system::error_code& ec, boost::asio::ip::tcp::socket socket) mutable {
            TCPSocketPtr sockPtr;
            if (!ec) {
    		    // 直接用 new 创建对象，然后用 reset 将所有权交给 unique_ptr
		    // BoostTCPSocket* 可以被安全地转换为 DPowerTCPSocket*
		    sockPtr.reset(new BoostTCPSocket(std::move(socket)));
		}
            h(BoostErrorCode(ec), std::move(sockPtr));
        });
    }
private:
    boost::asio::ip::tcp::acceptor acceptor_;
};


// ---------------------------------------------
// BoostNetFactory
// ---------------------------------------------
class BoostNetFactory : public DPowerNetFactory {
public:
    IOContextPtr CreateIO() override {
        return std::make_unique<BoostIOContext>();
    }

    TCPEndpointPtr CreateEndpoint(const std::string& addr, uint16_t port) override {
        return std::make_unique<BoostTCPEndpoint>(addr, port);
    }

    TCPAcceptorPtr CreateAcceptor(DPowerIOContext& io, const DPowerTCPEndpoint& ep) override {
        auto& bio = dynamic_cast<BoostIOContext&>(io);
        auto& bep = dynamic_cast<const BoostTCPEndpoint&>(ep);
        // 直接创建并返回正确的 Acceptor 类型
        return std::make_unique<BoostTCPAcceptor>(bio.Raw(), bep.Raw());
    }

    TCPSocketPtr CreateSocket(DPowerIOContext& io) override {
        auto& bio = dynamic_cast<BoostIOContext&>(io);
        return TCPSocketPtr(new BoostTCPSocket(boost::asio::ip::tcp::socket(bio.Raw())));
    }
};

//---------------------------------------------
// 外部可见工厂函数
//---------------------------------------------
NetFactoryPtr CreateBoostNetFactory() {
    return std::make_unique<BoostNetFactory>();
}

} // namespace Net
} // namespace DPower 
