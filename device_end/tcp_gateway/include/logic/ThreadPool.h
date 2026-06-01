#pragma once

#include <vector>
#include <queue>
#include <thread>
#include <mutex>
#include <condition_variable>
#include <functional>
#include <stdexcept>
#include <memory>

class ThreadPool {
public:
    // 构造函数：创建指定数量的工作线程
    ThreadPool(size_t threads = std::thread::hardware_concurrency(), 
               size_t max_queue_size = 10000) // 添加队列大小限制
        : stop(false), max_queue_size_(max_queue_size), dropped_tasks_(0) {
        if (threads == 0) {
            threads = 1; // 至少保证有一个线程
        }
        for(size_t i = 0; i < threads; ++i) {
            workers.emplace_back([this] {
                // 每个工作线程的执行循环
                while(true) {
                    std::function<void()> task;
                    {
                        // 独占锁，等待任务或线程池停止信号
                        std::unique_lock<std::mutex> lock(this->queue_mutex);
                        this->condition.wait(lock, [this]{ return this->stop || !this->tasks.empty(); });
                        
                        // 如果线程池已停止且任务队列为空，则退出循环
                        if(this->stop && this->tasks.empty()) {
                            return;
                        }

                        // 从队列中取出一个任务
                        task = std::move(this->tasks.front());
                        this->tasks.pop();
                    }
                    // 执行任务
                    task();
                }
            });
        }
    }

    // 提交新任务到队列，带队列大小限制
    bool post(std::function<void()> f) {
        {
            std::unique_lock<std::mutex> lock(queue_mutex);
            // 不允许在停止后添加新任务
            if(stop) {
                return false;
            }
            
            // 检查队列是否已满，如果满了就丢弃任务
            if(tasks.size() >= max_queue_size_) {
                ++dropped_tasks_;
                return false; // 任务被丢弃
            }
            
            tasks.emplace(std::move(f));
        }
        condition.notify_one(); // 唤醒一个等待的线程
        return true; // 任务成功入队
    }
    
    // 获取队列统计信息
    size_t queue_size() const {
        std::unique_lock<std::mutex> lock(queue_mutex);
        return tasks.size();
    }
    
    size_t dropped_count() const {
        std::unique_lock<std::mutex> lock(queue_mutex);
        return dropped_tasks_;
    }

    // 析构函数：停止并销毁线程池
    ~ThreadPool() {
        {
            std::unique_lock<std::mutex> lock(queue_mutex);
            stop = true;
        }
        condition.notify_all(); // 唤醒所有线程
        for(std::thread &worker: workers) {
            worker.join(); // 等待所有线程执行完毕
        }
    }

private:
    std::vector<std::thread> workers;
    std::queue<std::function<void()>> tasks;
    
    mutable std::mutex queue_mutex; // 添加mutable以支持const方法
    std::condition_variable condition;
    bool stop;
    
    // 新增成员变量
    size_t max_queue_size_;
    mutable size_t dropped_tasks_;
};
