import pytest
from mock import Mock
from python_graphql_subscriptions import SubscriptionManager, PubSub
from flask_socketio import SocketIOTestClient
import json

from tests.app import create_app
from tests.schema import Schema
from flask_graphql_subscriptions_transport.flask_graphql_subscriptions_transport import SubscriptionServer
from flask_graphql_subscriptions_transport.message_types import (
    SUBSCRIPTION_MESSAGE,
    SUBSCRIPTION_FAIL,
    SUBSCRIPTION_DATA,
    SUBSCRIPTION_START,
    SUBSCRIPTION_END,
    SUBSCRIPTION_SUCCESS,
    KEEPALIVE,
    INIT,
    INIT_FAIL,
    INIT_SUCCESS,
    PARAMS_MUST_BE_OBJECT,
)

###
# testing SubscriptionServer
###

# should use a default namespace if one is not provided
def test_default_namespace():
    schema = 'schema'
    pubsub = 'pubsub'
    setup_functions = {}
    sub_manager = SubscriptionManager(
        schema,
        pubsub,
        setup_functions,
    )
    app = create_app()
    ss = SubscriptionServer(app, sub_manager)
    assert ss.namespace == '/ws'

# should correctly initialize with the various arguments
def test_init():
    schema = 'schema'
    pubsub = 'pubsub'
    setup_functions = {}
    namespace='/foo'
    on_subscribe='on_subscribe'
    on_unsubscribe='on_unsubscribe'
    on_connect='on_connect'
    on_disconnect='on_disconnect'
    parse_context='parse_context'
    sub_manager = SubscriptionManager(
        schema,
        pubsub,
        setup_functions,
    )
    app = create_app()
    ss = SubscriptionServer(app,
                            sub_manager,
                            namespace,
                            on_subscribe,
                            on_unsubscribe,
                            on_connect,
                            on_disconnect,
                            parse_context)
    assert ss.subscription_manager == sub_manager
    assert ss.namespace == namespace
    assert ss.on_subscribe == on_subscribe
    assert ss.on_unsubscribe == on_unsubscribe
    assert ss.on_connect == on_connect
    assert ss.on_disconnect == on_disconnect
    assert ss.parse_context == parse_context

@pytest.fixture
def basic_ss():
    schema = Schema
    pubsub = PubSub()
    setup_functions = {}
    namespace='/foo'
    on_subscribe=lambda parsed_message, base_params: base_params
    on_unsubscribe=lambda *args, **kwargs: True
    on_connect=lambda *args, **kwargs: True
    on_disconnect=lambda *args, **kwargs: True
    parse_context=lambda *args, **kwargs: True
    sub_manager = SubscriptionManager(
        schema,
        pubsub,
        setup_functions,
    )
    app = create_app()
    ss = SubscriptionServer(app,
                            sub_manager,
                            namespace,
                            on_subscribe,
                            on_unsubscribe,
                            on_connect,
                            on_disconnect,
                            parse_context)
    return (app, ss)

# should respond to the connect event by sending data
def test_connect_response(basic_ss):
    app, ss = basic_ss
    ss.socketio.emit = Mock()
    ss.socket_connect()
    ss.socketio.emit.assert_called_once_with('message',
        {'data': 'connected'},
        namespace=ss.namespace)

# should respond to the disconnect event
def test_disconnect_response(basic_ss):
    app, ss = basic_ss
    ss.socketio.emit = Mock()
    ss.socket_disconnect()
    ss.socketio.emit.assert_called_once_with('message',
        {'data': 'disconnected'},
        namespace=ss.namespace)

# lots to do here...
# this just tests that the on_message method gets executed
def test_message_response():
    pass

# should send failure to the client if there is a bad message
def test_fails_on_invalid_message(basic_ss):
    app, ss = basic_ss
    test_client = SocketIOTestClient(app, ss.socketio, namespace=ss.namespace)
    ss.send_subscription_fail = Mock()
    test_client.emit('message',
                     {'already a': 'python object'},
                     namespace=ss.namespace)
    ss.send_subscription_fail.assert_called_once()

###
# INIT testing
###
# should execute the on_connect hook if provided
def test_executes_on_connect_hook(basic_ss):
    app, ss = basic_ss
    test_client = SocketIOTestClient(app, ss.socketio, namespace=ss.namespace)
    ss.on_connect = Mock(return_value=True)
    test_client.emit('message',
                     json.dumps({'type': INIT, 'payload': 'foo'}),
                     namespace=ss.namespace)
    ss.on_connect.assert_called_once()

def test_can_deny_init(basic_ss):
    app, ss = basic_ss
    test_client = SocketIOTestClient(app, ss.socketio, namespace=ss.namespace)
    ss.on_connect = Mock(return_value=False)
    ss.send_init_result = Mock(return_value=True)
    test_client.emit('message',
                     json.dumps({'type': INIT, 'payload': 'foo'}),
                     namespace=ss.namespace)
    ss.send_init_result.assert_called_once()
    assert INIT_FAIL == ss.send_init_result.call_args[0][0]

def test_valid_init_succeeds(basic_ss):
    app, ss = basic_ss
    test_client = SocketIOTestClient(app, ss.socketio, namespace=ss.namespace)
    ss.on_connect = Mock(return_value=True)
    ss.send_init_result = Mock(return_value=True)
    test_client.emit('message',
                     json.dumps({'type': INIT, 'payload': 'foo'}),
                     namespace=ss.namespace)
    ss.send_init_result.assert_called_once()
    assert INIT_SUCCESS == ss.send_init_result.call_args[0][0]

###
# SUBSCRIPTION_START testing
###
def test_parse_context_hook(basic_ss):
    app, ss = basic_ss
    test_client = SocketIOTestClient(app, ss.socketio, namespace=ss.namespace)
    ss.parse_context = Mock(return_value={})
    ss.send_subscription_success = Mock()
    test_client.emit('message',
                     json.dumps({'type': SUBSCRIPTION_START,
                                 'payload': 'foo',
                                 'query': 'query test{ testString }',
                                 'variables': 'baz'}),
                     namespace=ss.namespace)
    ss.parse_context.assert_called_once()
    ss.send_subscription_success.assert_called_once()

def test_on_subscribe_hook(basic_ss):
    app, ss = basic_ss
    test_client = SocketIOTestClient(app, ss.socketio, namespace=ss.namespace)
    ss.on_subscribe = Mock(return_value={'type': SUBSCRIPTION_START,
                                         'payload': 'foo',
                                         'query': 'query test{ testString }',
                                         'variables': 'baz'})
    ss.send_subscription_success = Mock()
    test_client.emit('message',
                     json.dumps({'type': SUBSCRIPTION_START,
                                 'payload': 'foo',
                                 'query': 'query test{ testString }',
                                 'variables': 'baz'}),
                     namespace=ss.namespace)
    ss.on_subscribe.assert_called_once()
    ss.send_subscription_success.assert_called_once()

# need a clever way to test this
def test_removes_old_subscriptions(basic_ss):
    pass

def test_base_params_rejected_if_not_dict(basic_ss):
    app, ss = basic_ss
    test_client = SocketIOTestClient(app, ss.socketio, namespace=ss.namespace)
    ss.on_subscribe = Mock(return_value='not a dict')
    ss.send_subscription_fail = Mock()
    test_client.emit('message',
                     json.dumps({'type': SUBSCRIPTION_START,
                                 'payload': 'foo',
                                 'query': 'query test{ testString }',
                                 'variables': 'baz'}),
                     namespace=ss.namespace)
    ss.on_subscribe.assert_called_once()
    ss.send_subscription_fail.assert_called_once()
    assert PARAMS_MUST_BE_OBJECT == ss.send_subscription_fail.call_args[0][1]['errors']

def test_subscribes_with_subscription_manager(basic_ss):
    app, ss = basic_ss
    test_client = SocketIOTestClient(app, ss.socketio, namespace=ss.namespace)
    ss.subscription_manager.subscribe = Mock()
    test_client.emit('message',
                     json.dumps({'type': SUBSCRIPTION_START,
                                 'payload': 'foo',
                                 'query': 'query test{ testString }',
                                 'variables': 'baz'}),
                     namespace=ss.namespace)
    ss.subscription_manager.subscribe.assert_called_once()

def test_callback_added_to_base_params(basic_ss):
    app, ss = basic_ss
    test_client = SocketIOTestClient(app, ss.socketio, namespace=ss.namespace)
    ss.subscription_manager.subscribe = Mock()
    test_client.emit('message',
                     json.dumps({'type': SUBSCRIPTION_START,
                                 'payload': 'foo',
                                 'query': 'query test{ testString }',
                                 'variables': 'baz'}),
                     namespace=ss.namespace)
    ss.subscription_manager.subscribe.assert_called_once()
    assert ss.subscription_manager.subscribe.call_args[1].get('callback', None) != None

def test_adds_unique_sub_id_to_subscriptions(basic_ss):
    app, ss = basic_ss
    test_client = SocketIOTestClient(app, ss.socketio, namespace=ss.namespace)
    test_client.emit('message',
                     json.dumps({'type': SUBSCRIPTION_START,
                                 'payload': 'foo',
                                 'id': 1,
                                 'query': 'query test{ testString }',
                                 'variables': 'baz'}),
                     namespace=ss.namespace)
    # get first item
    for key, val in ss.connection_subscriptions.items():
        first_key = key
        first_sub = ss.connection_subscriptions[key]
    del ss.connection_subscriptions[first_key]
    test_client.emit('message',
                     json.dumps({'type': SUBSCRIPTION_START,
                                 'payload': 'bar',
                                 'id': 2,
                                 'query': 'query test{ testString }',
                                 'variables': 'baz'}),
                     namespace=ss.namespace)
    # get second item
    for key, val in ss.connection_subscriptions.items():
        second_sub = ss.connection_subscriptions[key]
    assert first_sub != second_sub

def test_sends_subscription_success(basic_ss):
    app, ss = basic_ss
    test_client = SocketIOTestClient(app, ss.socketio, namespace=ss.namespace)
    ss.send_subscription_success = Mock()
    test_client.emit('message',
                     json.dumps({'type': SUBSCRIPTION_START,
                                 'payload': 'foo',
                                 'query': 'query test{ testString }',
                                 'variables': 'baz'}),
                     namespace=ss.namespace)
    ss.send_subscription_success.assert_called_once()

def test_sends_subscription_failure_on_unknown_message_type(basic_ss):
    app, ss = basic_ss
    test_client = SocketIOTestClient(app, ss.socketio, namespace=ss.namespace)
    ss.send_subscription_fail = Mock()
    test_client.emit('message',
                     json.dumps({'type': 'unknown message type',
                                 'payload': 'foo',
                                 'query': 'query test{ testString }',
                                 'variables': 'baz'}),
                     namespace=ss.namespace)
    ss.send_subscription_fail.assert_called_once()
    assert ss.send_subscription_fail.call_args[0][1] == {'errors': 'Invalid message type'}

def test_sends_subscription_failure_on_bad_query(basic_ss):
    app, ss = basic_ss
    test_client = SocketIOTestClient(app, ss.socketio, namespace=ss.namespace)
    ss.send_subscription_fail = Mock()
    test_client.emit('message',
                     json.dumps({'type': SUBSCRIPTION_START,
                                 'payload': 'foo',
                                 'query': 'query test{ unknownField }',
                                 'variables': 'baz'}),
                     namespace=ss.namespace)
    ss.send_subscription_fail.assert_called_once()

def test_sends_subscription_failure_on_missing_parameters(basic_ss):
    app, ss = basic_ss
    test_client = SocketIOTestClient(app, ss.socketio, namespace=ss.namespace)
    ss.send_subscription_fail = Mock()
    # not sending a variables param
    test_client.emit('message',
                     json.dumps({'type': SUBSCRIPTION_START,
                                 'payload': 'foo',
                                 'query': 'query test{ testString }'}),
                     namespace=ss.namespace)
    ss.send_subscription_fail.assert_called_once()

###
# SUBSCRIPTION_END testing
###
def test_calls_unsubscribe(basic_ss):
    app, ss = basic_ss
    test_client = SocketIOTestClient(app, ss.socketio, namespace=ss.namespace)
    ss.unsubscribe = Mock()
    test_client.emit('message',
                     json.dumps({'type': SUBSCRIPTION_START,
                                 'payload': 'foo',
                                 'id': 1,
                                 'query': 'query test{ testString }',
                                 'variables': 'baz'}),
                     namespace=ss.namespace)
    test_client.emit('message',
                     json.dumps({'type': SUBSCRIPTION_END,
                                 'payload': 'foo',
                                 'id': 1,}),
                     namespace=ss.namespace)
    ss.unsubscribe.assert_called_once()

def test_removes_subscription_id(basic_ss):
    app, ss = basic_ss
    test_client = SocketIOTestClient(app, ss.socketio, namespace=ss.namespace)
    assert len(ss.connection_subscriptions) == 0
    test_client.emit('message',
                     json.dumps({'type': SUBSCRIPTION_START,
                                 'payload': 'foo',
                                 'id': 1,
                                 'query': 'query test{ testString }',
                                 'variables': 'baz'}),
                     namespace=ss.namespace)
    assert len(ss.connection_subscriptions) == 1
    test_client.emit('message',
                     json.dumps({'type': SUBSCRIPTION_END,
                                 'payload': 'foo',
                                 'id': 1,}),
                     namespace=ss.namespace)
    assert len(ss.connection_subscriptions) == 0

###
# sending testing
###
# should send the appropriate data to the relevant client
def test_send_sub_data(basic_ss):
    app, ss = basic_ss
    test_client = SocketIOTestClient(app, ss.socketio, namespace=ss.namespace)
    test_client.emit('message',
                     json.dumps({'type': SUBSCRIPTION_START,
                                 'payload': 'foo',
                                 'id': 1,
                                 'query': 'query test{ testString }',
                                 'variables': {'some': 'vars'}}),
                     namespace=ss.namespace)
    ss.send_subscription_data = Mock()
    ss.subscription_manager.pubsub.publish('testString', {'foo': 'bar'})
    ss.send_subscription_data.assert_called_once()
    # should return what we expect based on our schema
    assert ss.send_subscription_data.call_args[0][1] == {'data':
        {'testString': 'string returned'}}

# should notify the client of subscription failure
def test_send_sub_fail(basic_ss):
    app, ss = basic_ss
    test_client = SocketIOTestClient(app, ss.socketio, namespace=ss.namespace)
    ss.send_subscription_fail = Mock()
    # not sending a query param
    test_client.emit('message',
                     json.dumps({'type': SUBSCRIPTION_START,
                                 'payload': 'foo',
                                 'id': 1,
                                 'variables': 'baz'}),
                     namespace=ss.namespace)
    ss.send_subscription_fail.assert_called_once()

# should notify the client of subscription success
def test_send_sub_success(basic_ss):
    app, ss = basic_ss
    test_client = SocketIOTestClient(app, ss.socketio, namespace=ss.namespace)
    ss.send_subscription_success = Mock()
    test_client.emit('message',
                     json.dumps({'type': SUBSCRIPTION_START,
                                 'payload': 'foo',
                                 'id': 1,
                                 'query': 'query test{ testString }',
                                 'variables': 'baz'}),
                     namespace=ss.namespace)
    ss.send_subscription_success.assert_called_once()

###
# INIT testing
###

def test_send_init_success(basic_ss):
    app, ss = basic_ss
    test_client = SocketIOTestClient(app, ss.socketio, namespace=ss.namespace)
    ss.send_init_result = Mock()
    test_client.emit('message',
                     json.dumps({'type': INIT,
                                 'id': 1,
                                 'payload': 'foo',}),
                     namespace=ss.namespace)
    ss.send_init_result.assert_called_once()
    assert ss.send_init_result.call_args[0][0] == INIT_SUCCESS

def test_send_init_fail(basic_ss):
    app, ss = basic_ss
    test_client = SocketIOTestClient(app, ss.socketio, namespace=ss.namespace)
    ss.send_init_result = Mock()
    ss.on_connect = Mock(return_value=False)
    test_client.emit('message',
                     json.dumps({'type': INIT,
                                 'id': 1,
                                 'payload': 'foo',}),
                     namespace=ss.namespace)
    ss.send_init_result.assert_called_once()
    assert ss.send_init_result.call_args[0][0] == INIT_FAIL
