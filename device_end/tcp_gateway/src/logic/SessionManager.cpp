#include "logic/SessionManager.h"
#include "logic/TCPSession.h"
#include "logic/utils/Logger.h"
#include <vector>

// 添加新会话的实现
void SessionManager::add(const std::string& id, std::shared_ptr<TCPSession> session) {
    // std::lock_guard 会在构造时自动加锁，在析构时（函数结束）自动解锁，确保线程安全
    std::lock_guard<std::mutex> lock(m_mutex);
    m_sessions[id] = session;
    Utils::Logger::Instance().Log(
        "INFO",
        "Session added: " + id + ". Total sessions: " + std::to_string(m_sessions.size()),
        "SessionManager");
}

// 移除会话的实现
void SessionManager::remove(const std::string& id) {
    std::lock_guard<std::mutex> lock(m_mutex);
    m_sessions.erase(id);
    Utils::Logger::Instance().Log(
        "INFO",
        "Session removed: " + id + ". Total sessions: " + std::to_string(m_sessions.size()),
        "SessionManager");
}

// 查找会话的实现
std::shared_ptr<TCPSession> SessionManager::find(const std::string& id) {
    std::lock_guard<std::mutex> lock(m_mutex);
    auto it = m_sessions.find(id);
    if (it != m_sessions.end()) {
        return it->second; // 返回找到的会话指针
    }
    return nullptr; // 没有找到，返回空指针
}

std::size_t SessionManager::count() const {
    std::lock_guard<std::mutex> lock(m_mutex);
    return m_sessions.size();
}

std::size_t SessionManager::force_close_all(const std::string& reason) {
    std::vector<std::shared_ptr<TCPSession>> sessions;
    {
        std::lock_guard<std::mutex> lock(m_mutex);
        sessions.reserve(m_sessions.size());
        for (auto& kv : m_sessions) {
            sessions.push_back(kv.second);
        }
    }

    for (auto& session : sessions) {
        if (session) {
            session->ForceClose(reason);
        }
    }

    Utils::Logger::Instance().Log(
        "WARN",
        "Force close requested for " + std::to_string(sessions.size()) +
            " sessions. reason=" + reason,
        "SessionManager");
    return sessions.size();
}