#include "logic/SessionManager.h"
#include <iostream>

// 添加新会话的实现
void SessionManager::add(const std::string& id, std::shared_ptr<TCPSession> session) {
    // std::lock_guard 会在构造时自动加锁，在析构时（函数结束）自动解锁，确保线程安全
    std::lock_guard<std::mutex> lock(m_mutex);
    m_sessions[id] = session;
    std::cout << "[SessionManager] Session added: " << id << ". Total sessions: " << m_sessions.size() << std::endl;
}

// 移除会话的实现
void SessionManager::remove(const std::string& id) {
    std::lock_guard<std::mutex> lock(m_mutex);
    m_sessions.erase(id);
    std::cout << "[SessionManager] Session removed: " << id << ". Total sessions: " << m_sessions.size() << std::endl;
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