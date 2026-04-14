from app.core.queue import Queue

q = Queue()

print("初始状态:", q)

q.enqueue("任务1")
q.enqueue("任务2")

print("入队后:", q)
print("队头元素:", q.peek())

print("出队:", q.dequeue())
print("出队:", q.dequeue())

print("最终状态:", q)

try:
    q.dequeue()
except IndexError as e:
    print("捕获异常成功:", e)