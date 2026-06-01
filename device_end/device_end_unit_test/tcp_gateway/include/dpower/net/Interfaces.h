#pragma once
// ================================================================
//  DPower::Net 抽象接口
//  业务层仅依赖这些纯虚接口，实现可由 Boost.Asio / libuv 等替换
// ================================================================

#include <cstdint>
#include <functional>
#include <memory>
#include <string>
#include <vector>

namespace DPower {
namespace Net {

//---------------------------------------------
// 前向声明 & 智能指针别名
//---------------------------------------------
class DPowerErrorCode;
class DPowerIOContext;
class DPowerTCPSocket;
class DPowerTCPAcceptor;
class DPowerTCPEndpoint;
class DPowerNetFactory;

using IOContextPtr   = std::unique_ptr<DPowerIOContext>;
using TCPSocketPtr   = std::unique_ptr<DPowerTCPSocket>;
using TCPAcceptorPtr = std::unique_ptr<DPowerTCPAcceptor>;
using TCPEndpointPtr = std::unique_ptr<DPowerTCPEndpoint>;
using NetFactoryPtr  = std::unique_ptr<DPowerNetFactory>;

//---------------------------------------------
// 抽象类型定义
//---------------------------------------------
class DPowerErrorCode {
public:
    virtual int         Value()   const = 0;
    virtual std::string Message() const = 0;
    virtual explicit operator bool() const = 0; // if(ec)
    virtual ~DPowerErrorCode() = default;
};

class DPowerIOContext {
public:
    virtual void Run()  = 0;
    virtual void Stop() = 0;
    // 添加 Post 方法以在IO线程上安全地调度任务
    virtual void Post(std::function<void()> f) = 0;
    virtual ~DPowerIOContext() = default;
};

class DPowerTCPEndpoint {
public:
    virtual std::string Address() const = 0;
    virtual uint16_t    Port()    const = 0;
    virtual ~DPowerTCPEndpoint() = default;
};

class DPowerTCPSocket {
public:
    struct MutableBuffer { void* data; std::size_t size; };
    using ReadHandler  = std::function<void(const DPowerErrorCode&, std::size_t)>;
    using WriteHandler = std::function<void(const DPowerErrorCode&, std::size_t)>;

    virtual void AsyncReadSome(MutableBuffer buf, ReadHandler handler)  = 0;
    virtual void AsyncWrite(const void* data, std::size_t len, WriteHandler handler) = 0;

    virtual std::string RemoteAddress() const = 0;
    virtual uint16_t    RemotePort()    const = 0;
    
    virtual void set_no_delay(bool enable) = 0;

    virtual void Close() = 0;
    virtual ~DPowerTCPSocket() = default;
};

class DPowerTCPAcceptor {
public:
    using AcceptHandler = std::function<void(const DPowerErrorCode&, TCPSocketPtr)>;
    virtual void AsyncAccept(AcceptHandler handler) = 0;
    virtual ~DPowerTCPAcceptor() = default;
};

class DPowerNetFactory {
public:
    virtual IOContextPtr   CreateIO() = 0;
    virtual TCPEndpointPtr CreateEndpoint(const std::string& addr, uint16_t port) = 0;
    virtual TCPAcceptorPtr CreateAcceptor(DPowerIOContext& io, const DPowerTCPEndpoint& ep) = 0;
    virtual TCPSocketPtr   CreateSocket(DPowerIOContext& io) = 0;
    virtual ~DPowerNetFactory() = default;
};

//---------------------------------------------
// 帮助函数
//---------------------------------------------
inline DPowerTCPSocket::MutableBuffer MakeMutableBuffer(void* data, std::size_t len) {
    return { data, len };
}

//---------------------------------------------
// 抽象层工厂获取函数（由各适配器实现）
//---------------------------------------------
NetFactoryPtr CreateBoostNetFactory();

} // namespace Net
} // namespace DPower

