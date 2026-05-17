"""Unit tests for the streaming module."""
import pytest
import asyncio
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from memory_system.core.streaming_memory_reader import (
    MemoryStreamer,
    StreamBuffer,
    StreamConfig,
    StreamResult,
)


class TestStreamConfig:
    def test_defaults(self):
        config = StreamConfig()
        assert config.batch_size == 10
        assert config.max_items is None
        assert config.buffer_size == 100

    def test_custom(self):
        config = StreamConfig(batch_size=5, max_items=20)
        assert config.batch_size == 5
        assert config.max_items == 20


class TestStreamResult:
    def test_create(self):
        result = StreamResult(items=[{"id": "1"}], batch_index=0, has_more=True)
        assert result.total_yielded == 0
        assert len(result.items) == 1


class TestMemoryStreamer:
    @pytest.mark.asyncio
    async def test_stream_from_list(self):
        data = [{"id": str(i)} for i in range(25)]
        streamer = MemoryStreamer(data, config=StreamConfig(batch_size=10))

        batches = []
        async for batch in streamer.stream():
            batches.append(batch)

        assert len(batches) == 3
        assert batches[0].batch_index == 0
        assert len(batches[0].items) == 10
        assert len(batches[1].items) == 10
        assert len(batches[2].items) == 5
        assert batches[2].has_more is False

    @pytest.mark.asyncio
    async def test_stream_with_max_items(self):
        data = [{"id": str(i)} for i in range(100)]
        streamer = MemoryStreamer(data, config=StreamConfig(batch_size=10, max_items=25))

        total = 0
        async for batch in streamer.stream():
            total += len(batch.items)

        assert total == 25

    @pytest.mark.asyncio
    async def test_stream_empty(self):
        streamer = MemoryStreamer([], config=StreamConfig(batch_size=10))

        batches = []
        async for batch in streamer.stream():
            batches.append(batch)

        assert len(batches) == 0

    @pytest.mark.asyncio
    async def test_stream_single_item(self):
        streamer = MemoryStreamer([{"id": "1"}], config=StreamConfig(batch_size=10))

        batches = []
        async for batch in streamer.stream():
            batches.append(batch)

        assert len(batches) == 1
        assert batches[0].has_more is False

    @pytest.mark.asyncio
    async def test_stream_from_callable_sync(self):
        def fetch(offset, limit):
            data = [{"id": str(i)} for i in range(offset, offset + limit)]
            if offset > 20:
                return []
            return data

        streamer = MemoryStreamer(fetch, config=StreamConfig(batch_size=5))

        total = 0
        async for batch in streamer.stream():
            total += len(batch.items)

        # offset=0 returns 5, offset=5 returns 5, offset=10 returns 5,
        # offset=15 returns 5, offset=20 returns 5 = 25 total
        assert total == 25

    @pytest.mark.asyncio
    async def test_stream_from_callable_async(self):
        async def fetch(offset, limit):
            await asyncio.sleep(0.001)
            return [{"id": str(i)} for i in range(offset, min(offset + limit, 15))]

        streamer = MemoryStreamer(fetch, config=StreamConfig(batch_size=5))

        total = 0
        async for batch in streamer.stream():
            total += len(batch.items)

        assert total == 15

    @pytest.mark.asyncio
    async def test_stream_callable_error(self):
        def fetch(offset, limit):
            raise RuntimeError("DB error")

        streamer = MemoryStreamer(fetch, config=StreamConfig(batch_size=5))

        batches = []
        async for batch in streamer.stream():
            batches.append(batch)

        assert len(batches) == 0

    @pytest.mark.asyncio
    async def test_collect_all(self):
        data = [{"id": str(i)} for i in range(7)]
        streamer = MemoryStreamer(data, config=StreamConfig(batch_size=3))

        result = await streamer.collect_all()
        assert len(result) == 7

    @pytest.mark.asyncio
    async def test_count(self):
        data = [{"id": str(i)} for i in range(50)]
        streamer = MemoryStreamer(data)
        assert await streamer.count() == 50

    @pytest.mark.asyncio
    async def test_count_with_max_items(self):
        data = [{"id": str(i)} for i in range(50)]
        streamer = MemoryStreamer(data, config=StreamConfig(max_items=10))
        assert await streamer.count() == 10

    @pytest.mark.asyncio
    async def test_count_unknown(self):
        streamer = MemoryStreamer(lambda o, l: [])
        assert await streamer.count() == -1


class TestStreamBuffer:
    @pytest.mark.asyncio
    async def test_write_and_read(self):
        buffer = StreamBuffer(max_size=10)

        await buffer.write({"id": "1"})
        await buffer.write({"id": "2"})
        buffer.finish()

        items = []
        async for item in buffer.read_stream():
            items.append(item)

        assert len(items) == 2
        assert items[0]["id"] == "1"

    @pytest.mark.asyncio
    async def test_write_batch(self):
        buffer = StreamBuffer()
        await buffer.write_batch([{"id": str(i)} for i in range(5)])
        buffer.finish()

        items = []
        async for item in buffer.read_stream():
            items.append(item)

        assert len(items) == 5

    @pytest.mark.asyncio
    async def test_empty_buffer(self):
        buffer = StreamBuffer()
        buffer.finish()

        items = []
        async for item in buffer.read_stream():
            items.append(item)

        assert len(items) == 0

    @pytest.mark.asyncio
    async def test_max_size(self):
        buffer = StreamBuffer(max_size=3)
        await buffer.write_batch([1, 2, 3, 4, 5])
        buffer.finish()

        # Should only keep last 3
        assert buffer.size == 3

    def test_size(self):
        buffer = StreamBuffer()
        assert buffer.size == 0

    def test_is_finished(self):
        buffer = StreamBuffer()
        assert buffer.is_finished is False
        buffer.finish()
        assert buffer.is_finished is True

    def test_clear(self):
        buffer = StreamBuffer()
        buffer._buffer.append(1)
        buffer._buffer.append(2)
        buffer.clear()
        assert buffer.size == 0
