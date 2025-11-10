from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, 
    from_json, 
    window, 
    count, 
    avg, 
    max as spark_max,
    min as spark_min,
    explode,
    split,
    lower
)
from pyspark.sql.types import (
    StructType, 
    StructField, 
    StringType, 
    DoubleType, 
    IntegerType
)
import time

# ===== INITIALIZE SPARK =====
# SparkSession = Entry point to Spark
# appName = Name shown in Spark UI
spark = SparkSession.builder \
    .appName("VoiceAIStreaming") \
    .getOrCreate()

# Suppress verbose logging
spark.sparkContext.setLogLevel("WARN")

print("✅ Spark Session Created")
print(f"Spark Version: {spark.version}")

# ===== DEFINE DATA SCHEMA =====
# This tells Spark what the JSON structure looks like
schema = StructType([
    StructField("timestamp", DoubleType(), True),           # When event happened
    StructField("datetime", StringType(), True),            # Human-readable time
    StructField("request_id", StringType(), True),          # Unique event ID
    StructField("text", StringType(), True),                # Text that was synthesized
    StructField("length", IntegerType(), True),             # Length of text
    StructField("filename", StringType(), True),            # Audio file created
    StructField("file_size", StringType(), True),           # Size of MP3 file
    StructField("voice_provider", StringType(), True),      # Which TTS (gTTS, pyttsx3, etc)
    StructField("processing_time", DoubleType(), True),     # How long it took
    StructField("success", StringType(), True)              # Did it work?
])

print("✅ Schema Defined")

# ===== READ STREAMING DATA =====
# Read JSON files from events folder in real-time
# maxFileAge = don't process files older than this
events_df = spark \
    .readStream \
    .schema(schema) \
    .json("events")

print("✅ Streaming Source Connected (watching 'events' folder)")

# ===== PARSE AND CLEAN DATA =====
# Convert timestamp to proper datetime format
from pyspark.sql.functions import from_unixtime, to_timestamp

events_parsed = events_df.select(
    col("timestamp"),
    to_timestamp(from_unixtime(col("timestamp"))).alias("event_time"),
    col("text"),
    col("length"),
    col("file_size"),
    col("voice_provider"),
    col("processing_time")
)

print("✅ Data Parsing Setup Complete")

# ===== ANALYTICS CALCULATION 1: Events Per Minute =====
# Window Function = Group data into time windows
# This groups events into 1-minute buckets and counts them

analytics_per_minute = events_parsed.groupBy(
    window(col("event_time"), "1 minute")  # 1-minute sliding window
).agg(
    count("*").alias("requests_per_minute"),
    avg("length").alias("avg_text_length"),
    spark_max("length").alias("max_text_length"),
    spark_min("length").alias("min_text_length"),
    avg("processing_time").alias("avg_processing_time_sec")
)

print("✅ Analytics 1: Events Per Minute - READY")

# ===== ANALYTICS CALCULATION 2: Word Frequency =====
# Split text into words and count frequency
# This shows which words are most commonly synthesized

word_frequency = events_parsed.select(
    explode(split(lower(col("text")), " ")).alias("word")
).groupBy("word").agg(
    count("*").alias("frequency")
).filter(col("word").rlike("^[a-z]{3,}$"))  # Only words with 3+ letters

print("✅ Analytics 2: Word Frequency - READY")

# ===== ANALYTICS CALCULATION 3: Text Length Distribution =====
# Show distribution of text lengths (short vs long requests)

length_distribution = events_parsed.groupBy(
    (col("length") / 50).cast(IntegerType()).alias("length_bucket")
).agg(
    count("*").alias("count")
).orderBy("length_bucket")

print("✅ Analytics 3: Length Distribution - READY")

# ===== WRITE OUTPUT TO CONSOLE =====
# outputMode = How to write results
# "update" = Only write changed rows (efficient)
# "complete" = Write entire result set (for debugging)

query1 = analytics_per_minute.writeStream \
    .outputMode("update") \
    .format("console") \
    .option("truncate", False) \
    .trigger(processingTime="10 seconds") \
    .start()

print("✅ Query 1 Started: Events Per Minute")

query2 = word_frequency.writeStream \
    .outputMode("complete") \
    .format("console") \
    .option("truncate", False) \
    .option("numRows", 10) \
    .trigger(processingTime="30 seconds") \
    .start()

print("✅ Query 2 Started: Word Frequency")

query3 = length_distribution.writeStream \
    .outputMode("complete") \
    .format("console") \
    .option("truncate", False) \
    .trigger(processingTime="15 seconds") \
    .start()

print("✅ Query 3 Started: Length Distribution")

print("\n" + "="*60)
print("🚀 SPARK STREAMING STARTED!")
print("="*60)
print("\n📊 Watching folder: events/")
print("📊 Update interval: 10-30 seconds")
print("📊 Ctrl+C to stop\n")

# ===== KEEP RUNNING =====
# awaitTermination() keeps the stream running forever
# It processes new events as they arrive

try:
    spark.streams.awaitAnyTermination()
except KeyboardInterrupt:
    print("\n\n⏹️ Stopping Spark Streaming...")
    spark.stop()
    print("✅ Spark Streaming Stopped")