const API_URL = "http://127.0.0.1:8000/predict"; // adjust if needed

// Chart.js setup
const ctx = document.getElementById("ageChart").getContext("2d");
const ageLabels = Array.from({length:31}, (_,i)=>i); // 0..30
let ageChart = new Chart(ctx, {
  type: "line",
  data: {
    labels: ageLabels,
    datasets: [{
      label: "Predicted Price (lakhs)",
      data: Array(ageLabels.length).fill(null),
      borderColor: "#4f46e5",
      backgroundColor: "rgba(79,70,229,0.08)",
      tension: 0.25,
      pointRadius: 3,
      fill: true
    }]
  },
  options: {
    responsive: true,
    scales: {
      x: { title: { display: true, text: "Car Age (years)" } },
      y: { title: { display: true, text: "Predicted Price (lakhs)" }, beginAtZero: true }
    },
    plugins: { legend: { display: false } }
  }
});

// Elements
const form = document.getElementById("car-form");
const predictBtn = document.getElementById("predict-btn");
const sweepBtn = document.getElementById("sweep-btn");
const predLarge = document.getElementById("prediction-large");
const predictionNote = document.getElementById("prediction-note");
const reliabilityEl = document.getElementById("reliability");
const flagBox = document.getElementById("flag-box");

function setLoading(on=true){
  predictBtn.disabled = on;
  sweepBtn.disabled = on;
  predictBtn.textContent = on ? "Predicting..." : "Predict Price";
}

// Helper: POST to /predict with payload { data: { ... } }
async function callPredict(payload){
  const res = await fetch(API_URL, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ data: payload })
  });
  if(!res.ok){
    const txt = await res.text();
    throw new Error("API error: " + txt);
  }
  return res.json();
}

// Show flags nicely
function renderFlags(flags){
  flagBox.innerHTML = "";
  if(!flags || Object.keys(flags).length===0){
    reliabilityEl.textContent = "✅ Good";
    reliabilityEl.className = "status good";
    return;
  }
  reliabilityEl.textContent = "⚠️ Low (OOR)";
  reliabilityEl.className = "status bad";
  const entries = Object.entries(flags);
  entries.forEach(([k,v])=>{
    const p = document.createElement("div");
    p.textContent = `${k}: ${JSON.stringify(v)}`;
    flagBox.appendChild(p);
  });
}

// Handle form submit (single predict + sweep)
form.addEventListener("submit", async (e) => {
  e.preventDefault();
  setLoading(true);
  predictionNote.textContent = "Calculating...";
  predLarge.textContent = "—";
  flagBox.innerHTML = "";

  const payloadBase = {
    Present_Price: parseFloat(document.getElementById("present_price").value),
    Kms_Driven: parseInt(document.getElementById("kms_driven").value),
    Car_Age: parseInt(document.getElementById("car_age").value),
    Fuel_Type: document.getElementById("fuel_type").value,
    Seller_Type: document.getElementById("seller_type").value,
    Transmission: document.getElementById("transmission").value,
    Owner: parseInt(document.getElementById("owner").value)
  };

  try{
    // Single prediction
    const res = await callPredict(payloadBase);
    predLarge.textContent = `${res.prediction.toFixed(2)} L`;
    predictionNote.textContent = `Reliability: ${res.reliability}`;
    renderFlags(res.flags);

    // Now run sweep for ages 0..30 (sequential)
    const preds = [];
    for(let age=0; age<=30; age++){
      const p = {...payloadBase, Car_Age: age};
      // compute Kms_per_Year roughly (server will compute if missing)
      // But sending Kms_per_Year is ok, server clamps as needed.
      p.Kms_per_Year = p.Kms_Driven / Math.max(1, p.Car_Age);
      try{
        const r = await callPredict(p);
        preds.push(Number(r.prediction.toFixed(4)));
      }catch(err){
        // if an individual age fails, push null and continue
        preds.push(null);
        console.warn("age", age, "failed:", err);
      }
    }
    // Update chart
    ageChart.data.datasets[0].data = preds;
    ageChart.update();

  }catch(err){
    predLarge.textContent = "Error";
    predictionNote.textContent = err.message;
    reliabilityEl.textContent = "⚠️";
    reliabilityEl.className = "status bad";
  } finally {
    setLoading(false);
  }
});

// Quick sweep button (only sweep for current form values)
sweepBtn.addEventListener("click", async (e)=>{
  e.preventDefault();
  // trigger same submit handler but without writing main single prediction UI
  document.getElementById("car-form").dispatchEvent(new Event('submit'));
});
