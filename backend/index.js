const mqtt = require('mqtt');
const { MongoClient } = require('mongodb');
require('dotenv').config();

const {
  MQTT_TOPIC,
  MONGO_URI,
  MONGO_DB,
  MONGO_COLLECTION
} = process.env;

// Połączenie z MongoDB
const mongoClient = new MongoClient(MONGO_URI);
let mongoCollection;

async function connectMongo() {
  try {
    await mongoClient.connect();
    const db = mongoClient.db(MONGO_DB);
    mongoCollection = db.collection(MONGO_COLLECTION);
    console.log("✅ Połączono z MongoDB");
  } catch (err) {
    console.error("❌ Błąd połączenia z MongoDB:", err);
  }
}

// Połączenie z brokerem MQTT
const mqttClient = mqtt.connect('mqtt://broker.emqx.io');

mqttClient.on('connect', () => {
  console.log("✅ Połączono z MQTT");
  mqttClient.subscribe(MQTT_TOPIC, (err) => {
    if (err) {
      console.error("❌ Błąd subskrypcji:", err);
    } else {
      console.log(`📡 Subskrybowano temat: ${MQTT_TOPIC}`);
    }
  });
});

mqttClient.on('message', async (topic, message) => {
  try {
    const data = JSON.parse(message.toString());
    console.log("📥 Odebrano dane:", data);

    if (mongoCollection) {
      await mongoCollection.insertOne({
        ...data,
        timestamp: new Date()
      });
      console.log("✅ Zapisano do MongoDB");
    }
  } catch (err) {
    console.error("❌ Błąd zapisu danych:", err);
  }
});
const express = require('express');
const cors = require('cors');
const app = express();
app.use(cors());
const PORT = process.env.PORT || 10000;

// Endpoint API: zwraca dane z MongoDB
app.get('/api/data', async (req, res) => {
  try {
    const data = await mongoCollection.find().sort({ timestamp: -1 }).limit(50).toArray();
    res.json(data);
  } catch (err) {
    console.error("❌ Błąd pobierania danych:", err);
    res.status(500).send("Błąd serwera");
  }
});

app.get('/', (req, res) => {
  res.send("MQTT Backend działa 🚀");
});

app.listen(PORT, () => {
  console.log(`🌐 Serwer nasłuchuje na porcie ${PORT}`);
});
// Startujemy!
connectMongo();
