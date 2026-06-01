#include "dpower/mq/Interfaces.h"

#include <memory>
#include <string>
#include <utility>
#include <mutex>          // 用于线程安全的锁
#include <unordered_set>  // 用于缓存已声明的队列

#ifdef USE_RABBITMQ_C
#include <amqp.h>
#include <amqp_framing.h>
#include <amqp_tcp_socket.h>
#endif

namespace DPower {
namespace MQ {

#ifdef USE_RABBITMQ_C
struct ParsedAmqpUri {
    std::string host;
    int port {5672};
    std::string user;
    std::string password;
    std::string vhost;
};

static bool ParseAmqpUri(const std::string& uri, ParsedAmqpUri& out, std::string& err) {
    const std::string prefix = "amqp://";
    if (uri.rfind(prefix, 0) != 0) {
        err = "Unsupported RabbitMQ URI, expected amqp://";
        return false;
    }

    std::string rest = uri.substr(prefix.size());
    size_t at_pos = rest.find('@');
    if (at_pos == std::string::npos) {
        err = "RabbitMQ URI missing credentials or host part";
        return false;
    }

    std::string auth = rest.substr(0, at_pos);
    std::string host_part = rest.substr(at_pos + 1);

    size_t colon_in_auth = auth.find(':');
    if (colon_in_auth == std::string::npos) {
        err = "RabbitMQ URI missing username/password";
        return false;
    }
    out.user = auth.substr(0, colon_in_auth);
    out.password = auth.substr(colon_in_auth + 1);

    size_t slash_pos = host_part.find('/');
    std::string host_port = host_part;
    out.vhost = "/";
    if (slash_pos != std::string::npos) {
        host_port = host_part.substr(0, slash_pos);
        std::string raw_vhost = host_part.substr(slash_pos + 1);
        if (!raw_vhost.empty()) {
            out.vhost = "/" + raw_vhost;
        }
    }

    size_t colon_in_host = host_port.rfind(':');
    if (colon_in_host == std::string::npos) {
        out.host = host_port;
    } else {
        out.host = host_port.substr(0, colon_in_host);
        try {
            out.port = std::stoi(host_port.substr(colon_in_host + 1));
        } catch (...) {
            err = "RabbitMQ URI has invalid port";
            return false;
        }
    }

    if (out.host.empty()) {
        err = "RabbitMQ URI host is empty";
        return false;
    }
    return true;
}

static std::string AmqpReplyErrorText(amqp_rpc_reply_t reply) {
    switch (reply.reply_type) {
        case AMQP_RESPONSE_NORMAL:
            return "";
        case AMQP_RESPONSE_NONE:
            return "missing RPC reply";
        case AMQP_RESPONSE_LIBRARY_EXCEPTION:
            return amqp_error_string2(reply.library_error);
        case AMQP_RESPONSE_SERVER_EXCEPTION:
            if (reply.reply.id == AMQP_CONNECTION_CLOSE_METHOD) {
                auto* m = static_cast<amqp_connection_close_t*>(reply.reply.decoded);
                return "server connection error: " + std::string(reinterpret_cast<char*>(m->reply_text.bytes), m->reply_text.len);
            }
            if (reply.reply.id == AMQP_CHANNEL_CLOSE_METHOD) {
                auto* m = static_cast<amqp_channel_close_t*>(reply.reply.decoded);
                return "server channel error: " + std::string(reinterpret_cast<char*>(m->reply_text.bytes), m->reply_text.len);
            }
            return "unknown server exception";
        default:
            return "unknown AMQP reply type";
    }
}

class RabbitMqClient : public DPowerMqClient {
public:
    RabbitMqClient() = default;

    ~RabbitMqClient() override {
        Disconnect();
    }

    DPowerMqResult Connect(const std::string& connection_uri) override {
        std::lock_guard<std::mutex> lock(mutex_); // 加锁保护连接建立

        DisconnectInternal();

        ParsedAmqpUri parsed;
        std::string err;
        if (!ParseAmqpUri(connection_uri, parsed, err)) {
            return {false, err};
        }

        conn_ = amqp_new_connection();
        if (!conn_) {
            return {false, "Failed to create RabbitMQ connection"};
        }

        amqp_socket_t* socket = amqp_tcp_socket_new(conn_);
        if (!socket) {
            DisconnectInternal();
            return {false, "Failed to create RabbitMQ TCP socket"};
        }

        if (amqp_socket_open(socket, parsed.host.c_str(), parsed.port) != AMQP_STATUS_OK) {
            DisconnectInternal();
            return {false, "Failed to open RabbitMQ socket"};
        }

        amqp_rpc_reply_t login_reply = amqp_login(conn_, parsed.vhost.c_str(), 0, 131072, 0,
                                                  AMQP_SASL_METHOD_PLAIN,
                                                  parsed.user.c_str(),
                                                  parsed.password.c_str());
        if (login_reply.reply_type != AMQP_RESPONSE_NORMAL) {
            std::string reply_err = AmqpReplyErrorText(login_reply);
            DisconnectInternal();
            return {false, "RabbitMQ login failed: " + reply_err};
        }

        amqp_channel_open(conn_, channel_);
        amqp_rpc_reply_t open_reply = amqp_get_rpc_reply(conn_);
        if (open_reply.reply_type != AMQP_RESPONSE_NORMAL) {
            std::string reply_err = AmqpReplyErrorText(open_reply);
            DisconnectInternal();
            return {false, "RabbitMQ open channel failed: " + reply_err};
        }

        connected_ = true;
        declared_queues_.clear(); // 连接成功后清空队列声明缓存
        return {true, ""};
    }

    void Disconnect() override {
        std::lock_guard<std::mutex> lock(mutex_);
        DisconnectInternal();
    }

    bool IsConnected() const override {
        std::lock_guard<std::mutex> lock(mutex_);
        return connected_ && conn_ != nullptr;
    }

    DPowerMqResult Publish(const std::string& queue_name,
                           const std::string& payload,
                           bool persistent) override {
        // 【核心修复 1】：全局互斥锁！彻底杜绝 32 个线程的 AMQP 帧交错踩踏
        std::lock_guard<std::mutex> lock(mutex_);

        if (!connected_ || !conn_) {
            return {false, "RabbitMQ is not connected"};
        }

        // 【核心修复 2】：队列声明缓存！防止对 RabbitMQ 的 DDoS 攻击
        if (declared_queues_.find(queue_name) == declared_queues_.end()) {
            amqp_queue_declare(conn_, channel_, amqp_cstring_bytes(queue_name.c_str()),
                               0,   // passive
                               1,   // durable
                               0,   // exclusive
                               0,   // auto_delete
                               amqp_empty_table);
            amqp_rpc_reply_t declare_reply = amqp_get_rpc_reply(conn_);
            if (declare_reply.reply_type != AMQP_RESPONSE_NORMAL) {
                return {false, "RabbitMQ queue_declare failed: " + AmqpReplyErrorText(declare_reply)};
            }
            declared_queues_.insert(queue_name); // 记录已声明，后续直接跳过
        }

        // 【极速发送路径】
        amqp_bytes_t message_bytes;
        message_bytes.len = payload.size();
        message_bytes.bytes = const_cast<char*>(payload.data());

        amqp_basic_properties_t props;
        props._flags = AMQP_BASIC_CONTENT_TYPE_FLAG | AMQP_BASIC_DELIVERY_MODE_FLAG;
        props.content_type = amqp_cstring_bytes("application/json");
        props.delivery_mode = persistent ? 2 : 1;

        int rc = amqp_basic_publish(conn_, channel_, amqp_empty_bytes,
                                    amqp_cstring_bytes(queue_name.c_str()),
                                    0, 0, &props, message_bytes);
        if (rc != AMQP_STATUS_OK) {
            return {false, "RabbitMQ publish failed"};
        }
        return {true, ""};
    }

private:
    // 内部无锁断开逻辑，供带锁的公共方法调用，防止死锁
    void DisconnectInternal() {
        if (conn_) {
            if (connected_) {
                amqp_channel_close(conn_, channel_, AMQP_REPLY_SUCCESS);
                amqp_connection_close(conn_, AMQP_REPLY_SUCCESS);
            }
            amqp_destroy_connection(conn_);
            conn_ = nullptr;
        }
        connected_ = false;
        declared_queues_.clear();
    }

    amqp_connection_state_t conn_ {nullptr};
    amqp_channel_t channel_ {1};
    bool connected_ {false};

    // 新增：线程安全保护
    mutable std::mutex mutex_;
    // 新增：已声明队列的 O(1) 查询缓存
    std::unordered_set<std::string> declared_queues_;
};

#else

class RabbitMqClient : public DPowerMqClient {
public:
    DPowerMqResult Connect(const std::string&) override {
        return {false, "RabbitMQ support is not enabled at build time (missing rabbitmq-c)"};
    }

    void Disconnect() override {}

    bool IsConnected() const override {
        return false;
    }

    DPowerMqResult Publish(const std::string&, const std::string&, bool) override {
        return {false, "RabbitMQ support is not enabled at build time (missing rabbitmq-c)"};
    }
};

#endif

class RabbitMqFactory : public DPowerMqFactory {
public:
    std::unique_ptr<DPowerMqClient> Create() override {
        return std::make_unique<RabbitMqClient>();
    }
};

std::unique_ptr<DPowerMqFactory> CreateRabbitMqFactory() {
    return std::make_unique<RabbitMqFactory>();
}

} // namespace MQ
} // namespace DPower
