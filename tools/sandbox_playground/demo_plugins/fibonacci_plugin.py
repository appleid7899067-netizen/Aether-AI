"""Sample plugin executed by Aether's PluginSandbox in its own process."""


class FibonacciPlugin:
    """Parameterised Fibonacci - shows params in / result out of the sandbox."""

    async def execute(self, params):
        count = int(params.get("count", 10))
        a, b = 0, 1
        series = []
        for _ in range(count):
            series.append(a)
            a, b = b, a + b
        return {
            "count": count,
            "series": series,
            "sum": sum(series),
            "ran_in": "separate process (PluginSandbox)",
        }
