const mqtt = require('mqtt');
const { MongoClient } = require('mongodb');
const express = require('express');
const app = express();

const PORT = process.env.PORT || 3000;

app.get('/', (_, res) => {
  res.send('Backend MQTT + MongoDB is running ✅');
});

app.listen(PORT, () => {
  console.log(`HTTP server listening on port ${PORT}`);
});
const {
  MQTT_HOST,
  MQTT_PORT,
  MQTT_USER,
  MQTT_PASS,
  MQTT_TOPIC,
  MONGO_URI,
  MONGO_DB,
  MONGO_COLLECTION
} = process.env;

const client = mqtt.connect(`mqtt://${MQTT_HOST}:${MQTT_PORT}`, {
  username: MQTT_USER,
  password: MQTT_PASS
});

const mongoClient = new MongoClient(MONGO_URI);

client.on('connect', () => {
  console.log('Połączono z MQTT');
  client.subscribe(MQTT_TOPIC, (err) => {
    if (err) {
      console.error('Błąd subskrypcji:', err);
    }
  });
});

client.on('message', async (topic, message) => {
  try {
    const data = JSON.parse(message.toString());
    const { napięcie1, napięcie2, prąd } = data;
    const moc = napięcie1 * prąd;
    const timestamp = new Date();

    await mongoClient.connect();
    const db = mongoClient.db(MONGO_DB);
    const collection = db.collection(MONGO_COLLECTION);

    await collection.insertOne({ napięcie1, napięcie2, prąd, moc, timestamp });
    console.log('Dane zapisane do MongoDB');
  } catch (error) {
    console.error('Błąd przetwarzania wiadomości:', error);
  }
});
