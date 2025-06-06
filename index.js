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

// Prosty serwer HTTP (potrzebny na Render)
const http = require('http');
const PORT = process.env.PORT || 10000;
http.createServer((req, res) => {
  res.writeHead(200);
  res.end("MQTT Backend działa 🚀");
}).listen(PORT, () => {
  console.log(`🌐 Serwer HTTP nasłuchuje na porcie ${PORT}`);
});

// Startujemy!
connectMongo();
