from ..utils import make_valid_data, correct_tags, with_dimensions


def process_firehose(location_info, client, agent):
    for delivery_stream_name in client.list_delivery_streams(Limit=10000).get("DeliveryStreamNames") or []:
        delivery_stream_raw = client.describe_delivery_stream(DeliveryStreamName=delivery_stream_name)
        delivery_stream = make_valid_data(delivery_stream_raw)
        delivery_stream_description = delivery_stream["DeliveryStreamDescription"]
        delivery_stream["Tags"] = (
            client.list_tags_for_delivery_stream(DeliveryStreamName=delivery_stream_name).get("Tags") or []
        )
        delivery_stream_arn = delivery_stream_description["DeliveryStreamARN"]
        delivery_stream_description.update(location_info)
        delivery_stream.update(location_info)
        delivery_stream.update(
            with_dimensions([{"key": "DeliveryStreamName", "value": delivery_stream_description["DeliveryStreamName"]}])
        )
        agent.component(delivery_stream_arn, "aws.firehose", correct_tags(delivery_stream))
        delivery_stream_type = delivery_stream_description["DeliveryStreamType"]

        if delivery_stream_type == "KinesisStreamAsSource":
            kinesis_stream_source = delivery_stream_description["Source"]["KinesisStreamSourceDescription"]
            kinesis_stream_arn = kinesis_stream_source["KinesisStreamARN"]
            agent.relation(kinesis_stream_arn, delivery_stream_arn, "uses service", {})

        for destination in delivery_stream_description["Destinations"]:
            s3_destination_description = destination.get("S3DestinationDescription")
            if s3_destination_description:
                bucket_arn = s3_destination_description["BucketARN"]
                agent.relation(delivery_stream_arn, bucket_arn, "uses service", {})
