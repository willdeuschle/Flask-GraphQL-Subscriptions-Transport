#
# implements the transport drop-in for python-graphql-subscriptions
#

# the websocket plugin we are using
from flask_socketio import SocketIO
from flask import request
import cgi
import json

from .message_types import (
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

class SubscriptionServer(object):
    def __init__(self,
                 app,
                 subscription_manager,
                 namespace='/ws',
                 on_subscribe=None,
                 on_unsubscribe=None,
                 on_connect=None,
                 on_disconnect=None,
                 parse_context=None,
                 **socket_options):

        # initialize
        self.subscription_manager = subscription_manager
        self.connection_subscriptions = {}
        self.namespace = namespace
        # hooks
        self.on_subscribe = on_subscribe
        self.on_unsubscribe = on_unsubscribe
        self.on_connect = on_connect
        self.on_disconnect = on_disconnect
        self.parse_context = parse_context

        # initialize websocket, and init with our app
        self.socketio = SocketIO()
        self.socketio.init_app(app)

        # connect
        self.socketio.on_event('connect', self.socket_connect, namespace=self.namespace)

        # disconnect
        self.socketio.on_event('disconnect', self.socket_disconnect, namespace=self.namespace)

        # run on a message
        self.socketio.on_event('message', self.on_message, namespace=self.namespace)

    # to run on connection
    def socket_connect(self):
        if self.on_connect:
            self.on_connect()
        self.socketio.emit('message', {'data': 'connected'}, namespace=self.namespace)

    # to run on disconnect
    def socket_disconnect(self):
        """
        cleans up all of the existing subscriptions
        """
        if self.on_disconnect:
            self.on_disconnect()
        self.socketio.emit('message', {'data': 'disconnected'}, namespace=self.namespace)

    def unsubscribe(self, sub_id):
        # delegate to our subscription_manager
        self.subscription_manager.unsubscribe(sub_id)
        # on_unsubscribe custom handler
        if self.on_unsubscribe:
            self.on_unsubscribe(sub_id)

    def on_message(self, message):
        """
        executes on message receipt
        handles the several reasons we would get a message:
        - INIT
        - SUBSCRIPTION_START
        - SUBSCRIPTION_END
        """

        # closure over request.sid
        request_id = request.sid

        # first parse our message
        try:
            parsed_message = json.loads(message)
        except Exception as e:
            # send failure
            self.send_subscription_fail(None, {'errors': e}, request_id)
            return

        sub_id = parsed_message.get('id', None)
        unique_sub_id = None
        # scope our subscription id here
        if sub_id is not None:
            unique_sub_id = str(request_id) + str(sub_id)

        # handle our different message types

        # INIT case
        if parsed_message['type'] == INIT:
            try:
                # custom set-up
                # can filter things out on INIT
                on_connect_context = True
                if self.on_connect:
                    on_connect_context = self.on_connect(parsed_message['payload'])

                if not on_connect_context:
                    raise ValueError('Prohibited connection!')

                self.send_init_result(INIT_SUCCESS, None, request_id)

            except Exception as e:
                self.send_init_result(INIT_FAIL, {'errors': e}, request_id)
            return


        # SUBSCRIPTION_START case
        elif parsed_message['type'] == SUBSCRIPTION_START:
            try:
                context = {}
                # gain general context from request if specified
                if self.parse_context:
                    context = self.parse_context(request)

                # query and variables required
                base_params = {
                     'query': parsed_message['query'],
                     'variables': parsed_message['variables'],
                     'operation_name': parsed_message.get('operation_name', None),
                     'context': context,
                     'format_response': None,
                     'format_error': None,
                     'callback': None,
                }
            except Exception as e:
                self.send_subscription_fail(sub_id,
                                            {'errors': repr(e)},
                                            request_id)
                return

            try:
                # option for custom on_subscribe
                if self.on_subscribe:
                    base_params = self.on_subscribe(parsed_message, base_params)

                # if we already have a subscription with this id unsub first
                # need a clever way to test this
                if self.connection_subscriptions.get(unique_sub_id, None):
                    self.unsubscribe(self.connection_subscriptions[unique_sub_id])
                    self.connection_subscriptions.pop(unique_sub_id)

                if not isinstance(base_params, dict):
                    self.send_subscription_fail(sub_id,
                                                {'errors': PARAMS_MUST_BE_OBJECT},
                                                request_id)
                    return

                # create a callback for sending data
                # error could be runtime or object with errors
                # result is GraphQL ExecutionResult
                def callback(error=None, result=None):
                    if not error:
                        self.send_subscription_data(sub_id, {'data': result.data}, request_id)
                    elif isinstance(error, dict) and 'errors' in error:
                        self.send_subscription_data(sub_id, {'errors': error['errors']}, request_id)
                    else:
                        # this is a runtime error
                        self.send_subscription_fail(sub_id, {'errors': error}, request_id)

                # set the callback
                base_params['callback'] = callback

                # get back the subscription id of the subscription_manager
                graphql_sub_id = self.subscription_manager.subscribe(**base_params)

                # add subscription
                self.connection_subscriptions[unique_sub_id] = graphql_sub_id

                self.send_subscription_success(sub_id, request_id)

            # handle any errors
            except Exception as e:
                if isinstance(e, dict):
                    # these are graphql errors
                    self.send_subscription_fail(sub_id, {'errors': e['errors']}, request_id)
                else:
                    # this is a runtime error
                    self.send_subscription_fail(sub_id, {'errors': e}, request_id)
            return

        # SUBSCRIPTION_END case
        elif parsed_message['type'] == SUBSCRIPTION_END:
            # get the sub_id, unsub, delete it
            if self.connection_subscriptions.get(unique_sub_id, None):
                self.unsubscribe(self.connection_subscriptions[unique_sub_id])
                self.connection_subscriptions.pop(unique_sub_id)
            return

        # otherwise fail
        else:
            self.send_subscription_fail(sub_id, {'errors': 'Invalid message type'}, request_id)
            return

    def send_subscription_data(self, sub_id, payload, request_id):
        """
        send update to the appropriate client via the session id
        """
        message = {
            'type': SUBSCRIPTION_DATA,
            'id': sub_id,
            'payload': payload,
            'room': request_id,
        }
        self.socketio.emit(SUBSCRIPTION_MESSAGE,
                          {'data': json.dumps(message)},
                          namespace=self.namespace,
                          room=request_id)

    def send_subscription_fail(self, sub_id, payload, request_id):
        """
        alert client to failure in setting up subscription
        """
        error_message = str(payload['errors'])
        message = {
            'type': SUBSCRIPTION_FAIL,
            'id': sub_id,
            'payload': error_message,
        }
        self.socketio.emit(SUBSCRIPTION_MESSAGE,
                          {'data': json.dumps(message)},
                          namespace=self.namespace,
                          room=request_id)

    def send_subscription_success(self, sub_id, request_id):
        """
        notify client of success in setting up subscription
        """
        message = {
            'type': SUBSCRIPTION_SUCCESS,
            'id': sub_id,
        }
        self.socketio.emit(SUBSCRIPTION_MESSAGE,
                          {'data': json.dumps(message)},
                          namespace=self.namespace,
                          room=request_id)

    def send_init_result(self, message_type, payload, request_id):
        if payload.get('errors', None):
            payload = str(payload['errors'])
        message = {
            'type': message_type,
            'payload': payload,
        }
        self.socketio.emit(SUBSCRIPTION_MESSAGE,
                          {'data': json.dumps(message)},
                          namespace=self.namespace,
                          room=request_id)
