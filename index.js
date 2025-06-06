require('dotenv').config();
const mqtt = require('mqtt');
const { MongoClient } = require('mongodb');
const http = require('http');

// === ENV ZMIENNE ===
const {
  MQTT_HOST,
  MQTT_PORT,
  MQTT_USER,
  MQTT_PASS,
  MQTT_TOPIC = 'projekt1-2/pw/dane',
  MQTT_STATUS_TOPIC = 'projekt1-2/pw/status',
  MONGO_URI,
  MONGO_DB,
  MONGO_COLLECTION
} = process.env;

// === MQTT KLIENT ===
const mqttClient = mqtt.connect({
  host: MQTT_HOST || 'broker.emqx.io',
  port: MQTT_PORT ? parseInt(MQTT_PORT) : 1883,
  username: MQTT_USER || undefined,
  password: MQTT_PASS || undefined,
  protocol: 'mqtt'
});

let deviceOnline = false;

// === MONGODB ===
const mongoClient = new MongoClient(MONGO_URI);
let collection;

async function initMongo() {
  try {
    await mongoClient.connect();
    const db = mongoClient.db(MONGO_DB);
    collection = db.collection(MONGO_COLLECTION);
    console.log('✅ Połączono z MongoDB');
  } catch (err) {
    console.error('❌ Błąd MongoDB:', err);
  }
}

initMongo();

// === MQTT EVENTY ===
mqttClient.on('connect', () => {
  console.log('✅ Połączono z MQTT');
  mqttClient.subscribe([MQTT_TOPIC, MQTT_STATUS_TOPIC], (err) => {
    if (err) {
      console.error('❌ Błąd subskrypcji:', err);
    } else {
      console.log(`📡 Subskrybowano: ${MQTT_TOPIC} i ${MQTT_STATUS_TOPIC}`);
    }
  });
});

mqttClient.on('message', async (topic, message) => {
  if (topic === MQTT_STATUS_TOPIC) {
    const status = message.toString();
    deviceOnline = status === 'online';
    console.log(`ℹ️ Status urządzenia: ${status}`);
    return;
  }

  if (topic === MQTT_TOPIC && deviceOnline) {
    try {
      const data = JSON.parse(message.toString());
      data.timestamp = new Date();
      await collection.insertOne(data);
      console.log('📥 Zapisano do MongoDB:', data);
    } catch (err) {
      console.error('❌ Błąd zapisu:', err);
    }
  } else {
    console.log('⚠️ Pominięto dane (offline)');
  }
});

// === HTTP SERVER dla Render ===
const PORT = process.env.PORT || 10000;
http.createServer((req, res) => {
  res.writeHead(200);
  res.end('MQTT backend działa\n');
}).listen(PORT, () => {
  console.log(`🌐 HTTP serwer działa na porcie ${PORT}`);
});
