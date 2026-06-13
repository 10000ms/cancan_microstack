"""
controllersrv 服务配置管理

存放程序运行时设置（不通过配置中心管理，只能修改代码）
"""
from cancan_microstack.public.const.controllersrv_consts import TimeoutKey


class ServiceSettings:
    """服务设置类"""

    # 超时配置（秒）
    TIMEOUT_CONFIG = {
        TimeoutKey.START: 300,  # 启动超时：5分钟
        TimeoutKey.STOP: 60,  # 停止超时：1分钟
        TimeoutKey.RESTART: 120,  # 重启超时：2分钟
        TimeoutKey.PS: 30,  # 查询超时：30秒
        TimeoutKey.CONFIG: 10,  # 配置读取超时：10秒
    }

    # 重试配置
    MAX_RETRIES = 3  # 最大重试次数
    RETRY_DELAY = 2  # 重试延迟（秒）

    # 任务配置
    TASK_MAX_EXECUTION_TIME = 1200  # 单个任务最大执行时间：20分钟
    TASK_QUEUE_MAX_SIZE = 100  # 任务队列最大容量
    TASK_CLEANUP_INTERVAL = 300  # 任务清理间隔：5分钟

    # Worker 配置
    WORKER_POLL_INTERVAL = 0.5  # Worker 轮询间隔（秒）
    WORKER_SHUTDOWN_TIMEOUT = 30  # Worker 关闭超时（秒）

    # 流水号配置
    SERIAL_NUMBER_MAX_AGE = 86400  # 流水号最大保留时间：24小时
    SERIAL_NUMBER_CLEANUP_INTERVAL = 3600  # 流水号清理间隔：1小时

    @classmethod
    def get_timeout(cls, operation_key: TimeoutKey) -> int:
        """
        获取指定操作的超时时间
        
        Args:
            operation_key: 操作类型键（TimeoutKey 枚举）
        
        Returns:
            超时时间（秒）
        """
        return cls.TIMEOUT_CONFIG.get(operation_key, 30)

    @classmethod
    def get_all_timeouts(cls) -> dict:
        """获取所有超时配置"""
        return cls.TIMEOUT_CONFIG.copy()
