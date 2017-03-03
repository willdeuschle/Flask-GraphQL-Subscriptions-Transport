# Flask-GraphQL-Subscriptions-Transport
Subscriptions transport for GraphQL applications using the Flask framework.

## Usage
This package serves as the transport mechanism for Flask applications that implement GraphQL subscriptions. It is designed for use with [Python-GraphQL-Subscriptions](https://github.com/willdeuschle/Python-GraphQL-Subscriptions), but it will work with any subscription manager that exposes publish/subscribe methods.

Use `SubscriptionServer` from `flask_graphql_subscriptions_transport`

```
from flask_graphql_subscriptions_transport import SubscriptionServer

app = Flask(__name__)

# SubscriptionManager from python_graphql_subscriptions
subscription_manager = SubscriptionManager(schema, pubsub, setup_functions) 

# instantiate the SubscriptionServer with your app and the subscription_manager
subscription_server = SubscriptionServer(app, subscription_manager)
```

To properly enable the subscriptions transport, which relies on [Flask-SocketIO](https://github.com/miguelgrinberg/Flask-SocketIO) for its websocket implementation, start your server like so:

```
# manage.py file #

from app import app, subscription_server

# enable asynchronicity
import eventlet
eventlet.monkey_patch()

.....

subscription_server.socketio.run(app,
  host=host,
  port=port,
  debug=use_debugger,
  use_reloader=use_reloader,
  **server_options)
```
