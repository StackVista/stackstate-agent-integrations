from ..utils import make_valid_data, correct_tags, with_dimensions


def process_sns(location_info, client, agent):
    sns = {}
    for topic_page in client.get_paginator('list_topics').paginate():
        for topic_data_raw in topic_page.get('Topics') or []:
            topic_data = make_valid_data(topic_data_raw)
            topic_arn = topic_data['TopicArn']
            topic_data['Name'] = topic_arn
            topic_name = topic_arn.rsplit(':', 1)[-1]
            topic_data.update(location_info)
            topic_data.update(with_dimensions([{'key': 'TopicName', 'value': topic_name}]))

            topic_data["Tags"] = client.list_tags_for_resource(ResourceArn=topic_arn)['Tags']

            agent.component(topic_arn, 'aws.sns', correct_tags(topic_data))
            sns[topic_name] = topic_arn
            for subscriptions_by_topicpage in client.get_paginator('list_subscriptions_by_topic').paginate(
                    TopicArn=topic_arn):
                for subscription_by_topic in subscriptions_by_topicpage.get('Subscriptions') or []:
                    if subscription_by_topic['Protocol'] in ['lambda', 'sqs'] and \
                            subscription_by_topic['TopicArn'] == topic_arn:
                        agent.relation(topic_arn, subscription_by_topic['Endpoint'], 'uses service', {})
    return sns
