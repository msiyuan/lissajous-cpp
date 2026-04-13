#ifndef THREAD_SAFE_QUEUE_H
#define THREAD_SAFE_QUEUE_H

#include <queue>
#include <mutex>
#include <condition_variable>
#include <optional>
#include <vector>

/**
 * 线程安全队列模板类
 * 支持多生产者多消费者模式
 */
template<typename T>
class ThreadSafeQueue {
public:
    explicit ThreadSafeQueue(size_t maxSize = 10000)
        : m_maxSize(maxSize), m_stopped(false) {}

    ~ThreadSafeQueue() {
        stop();
    }

    /**
     * 向队列添加元素（非阻塞）
     * @return true 成功，false 队列已满或已停止
     */
    bool tryPush(T item) {
        std::lock_guard<std::mutex> lock(m_mutex);
        if (m_stopped || m_queue.size() >= m_maxSize) {
            return false;
        }
        m_queue.push(std::move(item));
        m_condition.notify_one();
        return true;
    }

    /**
     * 向队列添加元素（阻塞）
     * @return true 成功，false 队列已停止
     */
    bool push(T item) {
        std::unique_lock<std::mutex> lock(m_mutex);
        m_condition.wait(lock, [this] {
            return m_stopped || m_queue.size() < m_maxSize;
        });
        if (m_stopped) {
            return false;
        }
        m_queue.push(std::move(item));
        m_condition.notify_one();
        return true;
    }

    /**
     * 从队列获取元素（非阻塞）
     * @return 元素，如果队列为空返回 std::nullopt
     */
    std::optional<T> tryPop() {
        std::lock_guard<std::mutex> lock(m_mutex);
        if (m_queue.empty()) {
            return std::nullopt;
        }
        T item = std::move(m_queue.front());
        m_queue.pop();
        m_condition.notify_one();
        return item;
    }

    /**
     * 从队列获取元素（阻塞）
     * @return 元素，如果队列已停止返回 std::nullopt
     */
    std::optional<T> pop() {
        std::unique_lock<std::mutex> lock(m_mutex);
        m_condition.wait(lock, [this] {
            return m_stopped || !m_queue.empty();
        });
        if (m_stopped && m_queue.empty()) {
            return std::nullopt;
        }
        T item = std::move(m_queue.front());
        m_queue.pop();
        m_condition.notify_one();
        return item;
    }

    /**
     * 批量获取多个元素（非阻塞）
     * @param maxCount 最大获取数量
     * @return 元素列表
     */
    std::vector<T> popBatch(size_t maxCount) {
        std::vector<T> items;
        std::lock_guard<std::mutex> lock(m_mutex);
        while (!m_queue.empty() && items.size() < maxCount) {
            items.push_back(std::move(m_queue.front()));
            m_queue.pop();
        }
        if (!items.empty()) {
            m_condition.notify_one();
        }
        return items;
    }

    /**
     * 获取队列大小
     */
    size_t size() const {
        std::lock_guard<std::mutex> lock(m_mutex);
        return m_queue.size();
    }

    /**
     * 检查队列是否为空
     */
    bool empty() const {
        std::lock_guard<std::mutex> lock(m_mutex);
        return m_queue.empty();
    }

    /**
     * 清空队列
     */
    void clear() {
        std::lock_guard<std::mutex> lock(m_mutex);
        while (!m_queue.empty()) {
            m_queue.pop();
        }
        m_condition.notify_all();
    }

    /**
     * 停止队列，唤醒所有等待的线程
     */
    void stop() {
        {
            std::lock_guard<std::mutex> lock(m_mutex);
            m_stopped = true;
        }
        m_condition.notify_all();
    }

    /**
     * 重新启动队列
     */
    void start() {
        std::lock_guard<std::mutex> lock(m_mutex);
        m_stopped = false;
    }

    bool isStopped() const {
        std::lock_guard<std::mutex> lock(m_mutex);
        return m_stopped;
    }

private:
    std::queue<T> m_queue;
    mutable std::mutex m_mutex;
    std::condition_variable m_condition;
    size_t m_maxSize;
    bool m_stopped;
};

#endif  // THREAD_SAFE_QUEUE_H
