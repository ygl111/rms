#include "dpower/http/Interfaces.h"

#include <boost/asio.hpp>
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

HttpResponse ParseHttpResponse(boost::asio::ip::tcp::socket& socket) {
    boost::asio::streambuf buf;
    boost::system::error_code ec;
    HttpResponse resp;

    // 读取 HTTP 响应头直到空行
    boost::asio::read_until(socket, buf, "\r\n\r\n", ec);
    if (ec && ec != boost::asio::error::eof) {
        resp.error_message = ec.message();
        return resp;
    }

    std::istream stream(&buf);
    
    // 解析状态行
    std::string http_version;
    unsigned int status_code = 0;
    stream >> http_version >> status_code;
    resp.status_code = static_cast<int>(status_code);
    
    // 读取完整状态行
    std::string status_message;
    std::getline(stream, status_message);
    
    // 跳过剩余的 headers（读取直到遇到空行）
    std::string header_line;
    while (std::getline(stream, header_line) && header_line != "\r" && !header_line.empty()) {
        // 可以在这里解析 Content-Length 等，暂时跳过
    }

    // 读取剩余内容（正文）- buf 中可能已经有一部分 body
    std::ostringstream body_ss;
    if (buf.size() > 0) {
        body_ss << &buf;
    }
    // 继续读取直到 EOF
    while (!ec) {
        boost::asio::read(socket, buf, boost::asio::transfer_at_least(1), ec);
        if (buf.size() > 0) {
            body_ss << &buf;
        }
    }
    resp.body = body_ss.str();
    
    // 去除 body 开头可能的空白字符
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
                          const std::string& bearer_token = "") override {
        HttpResponse resp;
        try {
            boost::asio::io_context io;
            boost::asio::ip::tcp::resolver resolver(io);
            auto endpoints = resolver.resolve(host, port);

            boost::asio::ip::tcp::socket socket(io);
            boost::asio::connect(socket, endpoints);

            auto request = BuildHttpRequest(host, target, json_body, bearer_token);
            boost::asio::write(socket, boost::asio::buffer(request));

            resp = ParseHttpResponse(socket);
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
