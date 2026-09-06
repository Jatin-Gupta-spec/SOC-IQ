"""
Tests for the Phase 4D SSE event infrastructure (app/application/broker.py,
app/application/events.py), per
docs/phase4/PHASE4D_SSE_ARCHITECTURE_DECISION.md and
docs/phase4/PHASE4D_SSE_PART1_IMPLEMENTATION.md.

Written with stdlib `unittest`, matching tests/test_application_layer.py's
existing convention (no pytest available in this sandbox -- see that
file's own docstring). Run with:

    python -m unittest tests.test_event_broker -v
"""

from __future__ import annotations

import threading
import time
import unittest

from app.application.broker import EventBroker, Subscription
from app.application.events import Event, EventCollector, new_correlation_id


def _make_event(name: str = "analysis.progress", **payload: object) -> Event:
    return Event.create(name, new_correlation_id("test"), dict(payload))


class EventContractTests(unittest.TestCase):
    """Stage 1: event_id addition is additive, not a redesign."""

    def test_event_has_event_id(self) -> None:
        event = _make_event()
        self.assertTrue(event.event_id)
        self.assertIsInstance(event.event_id, str)

    def test_event_id_is_unique_per_event(self) -> None:
        first = _make_event()
        second = _make_event()
        self.assertNotEqual(first.event_id, second.event_id)

    def test_event_id_included_in_to_dict(self) -> None:
        event = _make_event()
        self.assertIn("event_id", event.to_dict())

    def test_existing_fields_unchanged(self) -> None:
        event = Event.create(
            "analysis.completed",
            "an-abc123",
            {"key": "value"},
            version=1,
            investigation_id=7,
        )
        self.assertEqual(event.event, "analysis.completed")
        self.assertEqual(event.version, 1)
        self.assertEqual(event.correlation_id, "an-abc123")
        self.assertEqual(event.investigation_id, 7)
        self.assertEqual(event.payload, {"key": "value"})

    def test_event_still_frozen(self) -> None:
        event = _make_event()
        with self.assertRaises(Exception):
            event.event = "mutated"  # type: ignore[misc]


class BrokerCreationTests(unittest.TestCase):
    def test_broker_creates_with_default_capacity(self) -> None:
        broker = EventBroker()
        self.assertEqual(broker.subscriber_count(), 0)

    def test_broker_creates_with_custom_capacity(self) -> None:
        broker = EventBroker(capacity=4)
        subscription = broker.subscribe()
        self.assertEqual(subscription.capacity, 4)


class SingleSubscriberTests(unittest.TestCase):
    def test_subscriber_receives_published_event(self) -> None:
        broker = EventBroker()
        subscription = broker.subscribe()
        event = _make_event()

        broker.publish(event)

        received = subscription.get(timeout=1.0)
        self.assertEqual(received, event)

    def test_subscriber_receives_nothing_before_publish(self) -> None:
        broker = EventBroker()
        subscription = broker.subscribe()

        received = subscription.get_nowait()
        self.assertIsNone(received)


class MultipleSubscriberTests(unittest.TestCase):
    def test_each_subscriber_gets_its_own_copy(self) -> None:
        broker = EventBroker()
        sub_a = broker.subscribe()
        sub_b = broker.subscribe()
        event = _make_event()

        broker.publish(event)

        self.assertEqual(sub_a.get(timeout=1.0), event)
        self.assertEqual(sub_b.get(timeout=1.0), event)

    def test_subscriber_isolation_one_draining_does_not_affect_other(
        self,
    ) -> None:
        broker = EventBroker()
        sub_a = broker.subscribe()
        sub_b = broker.subscribe()
        event = _make_event()

        broker.publish(event)
        sub_a.get(timeout=1.0)

        self.assertEqual(len(sub_a), 0)
        self.assertEqual(len(sub_b), 1)

    def test_unsubscribing_one_does_not_affect_other(self) -> None:
        broker = EventBroker()
        sub_a = broker.subscribe()
        sub_b = broker.subscribe()

        broker.unsubscribe(sub_a)
        broker.publish(_make_event())

        self.assertIsNone(sub_a.get_nowait())
        self.assertIsNotNone(sub_b.get_nowait())


class OrderingTests(unittest.TestCase):
    def test_fifo_ordering_within_one_subscriber(self) -> None:
        broker = EventBroker()
        subscription = broker.subscribe()
        events = [_make_event(f"e.{i}") for i in range(10)]

        for event in events:
            broker.publish(event)

        received = [subscription.get_nowait() for _ in range(10)]
        self.assertEqual(received, events)

    def test_no_cross_subscriber_ordering_guarantee_is_assumed(self) -> None:
        """
        Per PHASE4D_SSE_ARCHITECTURE_DECISION.md S6 Ordering: only
        per-subscriber FIFO is guaranteed, not a global order across
        subscribers. This test asserts the one guarantee that DOES hold
        (each subscriber individually sees its own events in publish
        order) without asserting anything about relative timing or
        interleaving *between* subscribers, which the architecture
        explicitly does not promise.
        """

        broker = EventBroker()
        sub_a = broker.subscribe()
        sub_b = broker.subscribe()
        events = [_make_event(f"e.{i}") for i in range(5)]

        for event in events:
            broker.publish(event)

        received_a = [sub_a.get_nowait() for _ in range(5)]
        received_b = [sub_b.get_nowait() for _ in range(5)]

        self.assertEqual(received_a, events)
        self.assertEqual(received_b, events)


class BoundedQueueTests(unittest.TestCase):
    def test_queue_never_exceeds_capacity(self) -> None:
        broker = EventBroker(capacity=5)
        subscription = broker.subscribe()

        for i in range(50):
            broker.publish(_make_event(f"e.{i}"))
            self.assertLessEqual(len(subscription), 5)

        self.assertEqual(len(subscription), 5)

    def test_drop_oldest_keeps_most_recent_events(self) -> None:
        broker = EventBroker(capacity=3)
        subscription = broker.subscribe()
        events = [_make_event(f"e.{i}") for i in range(5)]

        for event in events:
            broker.publish(event)

        received = [subscription.get_nowait() for _ in range(3)]
        self.assertEqual(received, events[-3:])

    def test_drop_oldest_increments_dropped_count(self) -> None:
        broker = EventBroker(capacity=3)
        subscription = broker.subscribe()

        for i in range(5):
            broker.publish(_make_event(f"e.{i}"))

        self.assertEqual(subscription.dropped_count, 2)

    def test_no_drop_when_under_capacity(self) -> None:
        broker = EventBroker(capacity=10)
        subscription = broker.subscribe()

        for i in range(3):
            broker.publish(_make_event(f"e.{i}"))

        self.assertEqual(subscription.dropped_count, 0)


class UnsubscribeTests(unittest.TestCase):
    def test_unsubscribed_subscriber_stops_receiving(self) -> None:
        broker = EventBroker()
        subscription = broker.subscribe()

        broker.unsubscribe(subscription)
        broker.publish(_make_event())

        self.assertIsNone(subscription.get_nowait())
        self.assertTrue(subscription.closed)

    def test_unsubscribe_removes_from_broker_count(self) -> None:
        broker = EventBroker()
        subscription = broker.subscribe()
        self.assertEqual(broker.subscriber_count(), 1)

        broker.unsubscribe(subscription)

        self.assertEqual(broker.subscriber_count(), 0)

    def test_double_unsubscribe_is_safe(self) -> None:
        broker = EventBroker()
        subscription = broker.subscribe()

        broker.unsubscribe(subscription)
        broker.unsubscribe(subscription)  # must not raise

        self.assertEqual(broker.subscriber_count(), 0)

    def test_repeated_subscribe_unsubscribe_cycles(self) -> None:
        broker = EventBroker()

        for _ in range(20):
            subscription = broker.subscribe()
            self.assertEqual(broker.subscriber_count(), 1)
            broker.unsubscribe(subscription)
            self.assertEqual(broker.subscriber_count(), 0)

    def test_context_manager_unsubscribes_on_exit(self) -> None:
        broker = EventBroker()

        with broker.subscription() as subscription:
            self.assertEqual(broker.subscriber_count(), 1)
            broker.publish(_make_event())
            self.assertIsNotNone(subscription.get_nowait())

        self.assertEqual(broker.subscriber_count(), 0)

    def test_context_manager_unsubscribes_on_exception(self) -> None:
        broker = EventBroker()

        with self.assertRaises(ValueError):
            with broker.subscription():
                self.assertEqual(broker.subscriber_count(), 1)
                raise ValueError("boom")

        self.assertEqual(broker.subscriber_count(), 0)


class PublishWithNoSubscribersTests(unittest.TestCase):
    def test_publish_with_no_subscribers_does_not_raise(self) -> None:
        broker = EventBroker()
        broker.publish(_make_event())  # must not raise

    def test_publish_with_no_subscribers_then_subscribe_gets_nothing(
        self,
    ) -> None:
        broker = EventBroker()
        broker.publish(_make_event())

        subscription = broker.subscribe()

        self.assertIsNone(subscription.get_nowait())


class ShutdownTests(unittest.TestCase):
    def test_shutdown_closes_existing_subscriptions(self) -> None:
        broker = EventBroker()
        subscription = broker.subscribe()

        broker.shutdown()

        self.assertTrue(subscription.closed)

    def test_shutdown_then_publish_does_not_raise(self) -> None:
        broker = EventBroker()
        broker.subscribe()
        broker.shutdown()

        broker.publish(_make_event())  # must not raise

    def test_shutdown_then_subscribe_returns_closed_subscription(
        self,
    ) -> None:
        broker = EventBroker()
        broker.shutdown()

        subscription = broker.subscribe()

        self.assertTrue(subscription.closed)
        self.assertEqual(broker.subscriber_count(), 0)

    def test_shutdown_wakes_blocked_getter(self) -> None:
        broker = EventBroker()
        subscription = broker.subscribe()
        result: list[Event | None] = []

        def blocked_get() -> None:
            result.append(subscription.get(timeout=5.0))

        thread = threading.Thread(target=blocked_get)
        thread.start()
        time.sleep(0.05)  # let the thread actually enter get()'s wait
        broker.shutdown()
        thread.join(timeout=2.0)

        self.assertFalse(thread.is_alive())
        self.assertEqual(result, [None])

    def test_double_shutdown_is_safe(self) -> None:
        broker = EventBroker()
        broker.subscribe()

        broker.shutdown()
        broker.shutdown()  # must not raise


class ConcurrencyTests(unittest.TestCase):
    def test_concurrent_publish_from_multiple_threads(self) -> None:
        broker = EventBroker(capacity=1000)
        subscription = broker.subscribe()
        events_per_thread = 50
        thread_count = 8

        def publish_many(thread_index: int) -> None:
            for i in range(events_per_thread):
                broker.publish(_make_event(f"t{thread_index}.e{i}"))

        threads = [
            threading.Thread(target=publish_many, args=(i,))
            for i in range(thread_count)
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=5.0)

        self.assertEqual(len(subscription), thread_count * events_per_thread)

    def test_concurrent_subscribe_unsubscribe_safety(self) -> None:
        broker = EventBroker()
        errors: list[BaseException] = []

        def churn() -> None:
            try:
                for _ in range(100):
                    subscription = broker.subscribe()
                    broker.publish(_make_event())
                    broker.unsubscribe(subscription)
            except BaseException as error:  # noqa: BLE001 -- test assertion,
                # intentionally broad: any exception here is a bug in the
                # broker's thread safety.
                errors.append(error)

        threads = [threading.Thread(target=churn) for _ in range(6)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10.0)

        self.assertEqual(errors, [])
        self.assertEqual(broker.subscriber_count(), 0)

    def test_concurrent_publish_does_not_cross_deliver_between_subscribers(
        self,
    ) -> None:
        broker = EventBroker(capacity=200)
        sub_a = broker.subscribe()
        sub_b = broker.subscribe()

        def publish_many() -> None:
            for i in range(100):
                broker.publish(_make_event(f"e.{i}"))

        thread = threading.Thread(target=publish_many)
        thread.start()
        thread.join(timeout=5.0)

        self.assertEqual(len(sub_a), 100)
        self.assertEqual(len(sub_b), 100)


class EventCollectorCompatibilityTests(unittest.TestCase):
    """
    Stage 3: EventCollector is untouched by this Part -- these tests
    exist to prove that fact, not to test new behavior. Per
    PHASE4D_SSE_ARCHITECTURE_DECISION.md S9, EventCollector remains a
    test-only helper; no handler was modified to also publish to a broker
    in this Part (see PHASE4D_SSE_PART1_IMPLEMENTATION.md for why that is
    out of scope here).
    """

    def test_event_collector_still_works_standalone(self) -> None:
        collector = EventCollector()
        event = _make_event()

        collector.publish(event)

        self.assertEqual(collector.events, [event])

    def test_event_collector_as_dicts_includes_new_event_id_field(
        self,
    ) -> None:
        collector = EventCollector()
        collector.publish(_make_event())

        dicts = collector.as_dicts()

        self.assertIn("event_id", dicts[0])

    def test_same_event_object_can_go_to_both_collector_and_broker(
        self,
    ) -> None:
        """
        Not a claim that any handler does this yet (none does, in this
        Part) -- only that the two sinks are independent and don't
        interfere with each other when both receive the same `Event`
        object, which is the shape S9's future handler integration will
        rely on.
        """

        collector = EventCollector()
        broker = EventBroker()
        subscription = broker.subscribe()
        event = _make_event()

        collector.publish(event)
        broker.publish(event)

        self.assertEqual(collector.events, [event])
        self.assertEqual(subscription.get_nowait(), event)


if __name__ == "__main__":
    unittest.main()
