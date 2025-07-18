import functools
from enum import Enum
from typing import Generic, TypeVar, ParamSpec, Callable
import uuid

T = TypeVar("T")
T_Retval = TypeVar("T_Retval")
T_ParamSpec = ParamSpec("T_ParamSpec")


class TaskStatus(Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class Task(Generic[T]):
    def __init__(
        self,
        func: Callable[..., T],
        id: str,
        status: TaskStatus = TaskStatus.PENDING,
        max_retries: int | None = None,
    ) -> None:
        super().__init__()
        self.func: Callable[..., T] = func
        self.id: str = id
        self.status: TaskStatus = status
        self.max_retries: int | None = max_retries
        self.result: T | None = None
        self.metadata: dict = {}

    def add_metadata(
        self,
        metadata: dict,
    ):
        self.metadata.update(metadata)

    def run(
        self,
    ) -> None:
        self.status = TaskStatus.RUNNING
        if self.max_retries:
            exception = None
            tried: int = 0
            # The number of retry time and the first run time
            for _ in range(self.max_retries + 1):
                try:
                    res = self.func()
                    self.result = res
                    self.status = TaskStatus.COMPLETED
                    return
                except Exception as e:
                    exception = e
                    tried += 1
            self.status = TaskStatus.FAILED
            self.add_metadata({"exception": exception})
            self.add_metadata({"retry": tried})

            return

        else:
            try:
                res = self.func()
                self.result = res
                self.status = TaskStatus.COMPLETED
                return
            except Exception as e:
                self.status = TaskStatus.FAILED
                self.add_metadata({"exception": e})
                return

    def run_in_loop(self):
        # TODO: in progress
        pass

    @staticmethod
    def create_task(
        func: Callable[T_ParamSpec, T_Retval],
        id: str | None = None,
        status: TaskStatus = TaskStatus.PENDING,
        max_retries: int | None = None,
    ) -> Callable[T_ParamSpec, "Task[T_Retval]"]:
        if id is None:
            id = str(uuid.uuid4)

        @functools.wraps(func)
        def wrapper(
            *args: T_ParamSpec.args,
            **kwagrs: T_ParamSpec.kwargs,
        ) -> "Task[T_Retval]":
            partial_function = functools.partial(func, *args, **kwagrs)

            return Task(
                func=partial_function, id=id, status=status, max_retries=max_retries
            )

        return wrapper


class TaskManager:
    def __init__(self) -> None:
        self.tasks: list[Task] = []
        self.completed_tasks: list[Task] = []
        self.failed_tasks: list[Task] = []

    def add_task(
        self,
        task: Task,
    ):
        self.tasks.append(task)

    def run_tasks(
        self,
    ):
        for task in self.tasks:
            task.run()
            if task.status is TaskStatus.COMPLETED:
                self.completed_tasks.append(task)
            elif task.status is TaskStatus.FAILED:
                self.failed_tasks.append(task)
