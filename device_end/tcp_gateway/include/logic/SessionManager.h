#pragma once

#include <string>
#include <memory>
#include <mutex>
#include <unordered_map>
#include <cstddef>

// 前置声明 TCPSession 类，避免在头文件中循环引用
class TCPSession;

// 线程安全的会话管理器
class SessionManager {
public:
    // 添加一个新的会话到管理器中
    // id: 会话的唯一标识符 (例如 "IP:Port")
    // session: 指向TCPSession对象的共享指针
    void add(const std::string& id, std::shared_ptr<TCPSession> session);

    // 从管理器中移除一个会话
    // id: 要移除的会话的唯一标识符
    void remove(const std::string& id);

    // 根据ID查找一个活跃的会话
    // id: 要查找的会话的唯一标识符
    // 返回: 如果找到，则返回指向该会话的共享指针；否则返回nullptr
    std::shared_ptr<TCPSession> find(const std::string& id);

    // 当前连接会话总数
    std::size_t count() const;

    // 强制断开所有会话，返回断开前会话数
    std::size_t force_close_all(const std::string& reason);

private:
    // 使用互斥锁(mutex)来保护m_sessions的并发访问
    mutable std::mutex m_mutex;
    
    // 使用哈希表(unordered_map)来存储ID到会话指针的映射，查找效率高
    std::unordered_map<std::string, std::shared_ptr<TCPSession>> m_sessions;
};