def pytask_self_test(vamos_task):
    """check if pytask feature works"""

    def task1(ctx, task):
        return 42

    def task2(ctx, task):
        return 23

    exit_codes = vamos_task.run([task1, task2])
    assert exit_codes == [42, 23]
