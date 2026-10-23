async function getWeather() {
    const city = document.getElementById("cityInput").value;
    if (!city) return alert("Please enter a city name.");

    try {
        const res = await fetch(`/weather?city=${city}`);
        const data = await res.json();

        if (data.error) {
            document.getElementById("result").innerText = data.error;
        } else {
            document.getElementById("result").innerHTML = `
                <h2>${data.name}, ${data.sys.country}</h2>
                <p>Temperature: ${data.main.temp}°C</p>
                <p>Weather: ${data.weather[0].description}</p>
                <p>Humidity: ${data.main.humidity}%</p>
                <p>Wind: ${data.wind.speed} m/s</p>
            `;
        }
    } catch (err) {
        document.getElementById("result").innerText = "Error fetching weather data.";
    }
}
