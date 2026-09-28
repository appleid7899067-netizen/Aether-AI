"""Sample plugin: quick text statistics, executed inside Aether's PluginSandbox."""


class TextStatsPlugin:
    """Counts characters/words and finds the most frequent word."""

    async def execute(self, params):
        text = str(params.get("text", "hello aether hello sandbox"))
        words = text.split()
        counts = {}
        for word in words:
            counts[word] = counts.get(word, 0) + 1
        top = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:3]
        return {
            "characters": len(text),
            "words": len(words),
            "unique_words": len(counts),
            "top_words": top,
            "ran_in": "separate process (PluginSandbox)",
        }
