from graphql.type.definition import GraphQLArgument, GraphQLField, GraphQLNonNull, GraphQLObjectType
from graphql.type.scalars import GraphQLString, GraphQLBoolean
from graphql.type.schema import GraphQLSchema

Query = GraphQLObjectType(
    name='Query',
    fields={
        'testString': GraphQLField(GraphQLNonNull(GraphQLString),
            resolver=lambda root, args, context, info: 'string returned'
        )
    }
)

Subscription = GraphQLObjectType(
    name='Subscription',
    fields={
        'test_subscription': GraphQLField(
            type=GraphQLNonNull(GraphQLString),
            resolver=lambda root, args, context, info: root
        ),
        'test_filter_sub': GraphQLField(
            type=GraphQLNonNull(GraphQLString),
            args={'filter_bool': GraphQLArgument(GraphQLBoolean)},
            resolver=lambda root, args, context, info: 'SUCCESS'
        ),
    }
)

Schema = GraphQLSchema(Query, subscription=Subscription)
