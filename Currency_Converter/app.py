from flask import Flask, render_template, request

app = Flask(__name__)

rates = {
    "USD": 1.0,
    "INR": 86.5,
    "EUR": 0.87,
    "GBP": 0.74
    
}

@app.route("/", methods=["GET", "POST"])
def home():
    result = ""

    if request.method == "POST":
        amount = float(request.form["amount"])
        from_currency = request.form["from"]
        to_currency = request.form["to"]

        usd = amount / rates[from_currency]
        converted = usd * rates[to_currency]

        result = f"{amount} {from_currency} = {converted:.2f} {to_currency}"

    return render_template("index.html", result=result)

if __name__ == "__main__": 
    app.run(debug=True)