#include "dpower/http/Interfaces.h"

#include <boost/asio.hpp>
#include <boost/asio/ssl.hpp>
#include <openssl/ssl.h>
#include <sstream>
#include <iostream>

namespace DPower {
namespace Http {

namespace {

std::string BuildHttpRequest(const std::string& host,
                             const std::string& target,
                             const std::string& body,
                             const std::string& bearer_token) {
    std::ostringstream oss;
    oss << "POST " << target << " HTTP/1.1\r\n";
    oss << "Host: " << host << "\r\n";
    oss << "User-Agent: cpp-parser/notification\r\n";
    oss << "Content-Type: application/json\r\n";
    if (!bearer_token.empty()) {
        oss << "Authorization: Bearer " << bearer_token << "\r\n";
    }
    oss << "Content-Length: " << body.size() << "\r\n";
    oss << "Connection: close\r\n\r\n";
    oss << body;
    return oss.str();
}

template <typename Stream>
HttpResponse ParseHttpResponse(Stream& stream) {
    boost::asio::streambuf buf;
    boost::system::error_code ec;
    HttpResponse resp;

    // 读取 HTTP 响应头，直到空行结束。
    boost::asio::read_until(stream, buf, "\r\n\r\n", ec);
    if (ec && ec != boost::asio::error::eof) {
        resp.error_message = ec.message();
        return resp;
    }

    std::istream response_stream(&buf);
    
    // 解析状态行。
    std::string http_version;
    unsigned int status_code = 0;
    response_stream >> http_version >> status_code;
    resp.status_code = static_cast<int>(status_code);
    
    // 读取状态描述文本。
    std::string status_message;
    std::getline(response_stream, status_message);
    
    // 读取剩余 headers，直到空行。
    std::string header_line;
    while (std::getline(response_stream, header_line) && header_line != "\r" && !header_line.empty()) {
        // 这里可按需解析 Content-Length 等头字段，当前先忽略。
    }

    // 读取响应体：buf 中可能已包含部分 body。
    std::ostringstream body_ss;
    if (buf.size() > 0) {
        body_ss << &buf;
    }
    // 持续读取直到 EOF。
    while (!ec) {
        boost::asio::read(stream, buf, boost::asio::transfer_at_least(1), ec);
        if (buf.size() > 0) {
            body_ss << &buf;
        }
    }
    resp.body = body_ss.str();
    
    // 去掉 body 开头可能存在的空白字符。
    size_t start = resp.body.find_first_not_of(" \t\r\n");
    if (start != std::string::npos) {
        resp.body = resp.body.substr(start);
    }
    
    return resp;
}

} // anonymous namespace

// ---------------------------------------------
// BoostHttpClient 实现
// ---------------------------------------------
class BoostHttpClient : public DPowerHttpClient {
public:
    BoostHttpClient() = default;
    ~BoostHttpClient() override = default;

    HttpResponse PostJson(const std::string& host,
                          const std::string& port,
                          const std::string& target,
                          const std::string& json_body,
                          const std::string& bearer_token = "",
                          bool use_https = false,
                          bool verify_tls = true) override {
        HttpResponse resp;
        try {
            boost::asio::io_context io;
            boost::asio::ip::tcp::resolver resolver(io);
            auto endpoints = resolver.resolve(host, port);

            auto request = BuildHttpRequest(host, target, json_body, bearer_token);

            if (use_https) {
                boost::asio::ssl::context ssl_ctx(boost::asio::ssl::context::tls_client);
                if (verify_tls) {
                    ssl_ctx.set_default_verify_paths();
                    ssl_ctx.set_verify_mode(boost::asio::ssl::verify_peer);
                } else {
                    ssl_ctx.set_verify_mode(boost::asio::ssl::verify_none);
                }

                boost::asio::ssl::stream<boost::asio::ip::tcp::socket> ssl_stream(io, ssl_ctx);
                if (!SSL_set_tlsext_host_name(ssl_stream.native_handle(), host.c_str())) {
                    resp.error_message = "Failed to set TLS SNI hostname";
                    return resp;
                }

                boost::asio::connect(ssl_stream.next_layer(), endpoints);
                ssl_stream.handshake(boost::asio::ssl::stream_base::client);
                boost::asio::write(ssl_stream, boost::asio::buffer(request));

                resp = ParseHttpResponse(ssl_stream);
            } else {
                boost::asio::ip::tcp::socket socket(io);
                boost::asio::connect(socket, endpoints);
                boost::asio::write(socket, boost::asio::buffer(request));

                resp = ParseHttpResponse(socket);
            }
        } catch (const std::exception& e) {
            resp.error_message = e.what();
            std::cerr << "[WARN] BoostHttpClient exception: " << e.what() << std::endl;
        }
        return resp;
    }
};

// ---------------------------------------------
// BoostHttpFactory 实现
// ---------------------------------------------
class BoostHttpFactory : public DPowerHttpFactory {
public:
    HttpClientPtr CreateHttpClient() override {
        return std::make_shared<BoostHttpClient>();
    }
};

// ---------------------------------------------
// 工厂函数实现
// ---------------------------------------------
HttpFactoryPtr CreateBoostHttpFactory() {
    return std::make_unique<BoostHttpFactory>();
}

} // namespace Http
} // namespace DPower
