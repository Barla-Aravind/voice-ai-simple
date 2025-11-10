from pyspark.sql import SparkSession
from pyspark.sql.functions import col, window, from_unixtime
from pyspark.sql.types import StructType, DoubleType, StringType, IntegerType

# Initialize Spark session
spark = SparkSession.builder.appName("VoiceAIStreaming").getOrCreate()

# Schema matches backend JSON
schema = StructType() \
    .add("timestamp", DoubleType()) \
    .add("text", StringType()) \
    .add("length", IntegerType()) \
    .add("filename", StringType())

# Read streaming data
df = spark.readStream \
    .format("json") \
    .schema(schema) \
    .load("events")

# Convert epoch seconds (double) -> proper timestamp
df = df.withColumn("event_time", from_unixtime(col("timestamp")).cast("timestamp"))
# Count requests per minute
analytics = df.groupBy(window(col("event_time"), "1 minute")).count()

# Write results to console
query = analytics.writeStream \
    .outputMode("complete") \
    .format("console") \
    .start()

query.awaitTermination()
