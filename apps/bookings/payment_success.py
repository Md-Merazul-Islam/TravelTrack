from django.http import HttpResponse


def payment_success(request):
    if request.method == 'GET':
        html_content = """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Payment Success</title>
            <style>
                body {
                    background: linear-gradient(135deg, #0070ba, #1546a0);
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    height: 100vh;
                    margin: 0;
                    font-family: Arial, sans-serif;
                }
                .card {
                    background: #fff;
                    border-radius: 20px;
                    padding: 40px;
                    text-align: center;
                    box-shadow: 0 8px 25px rgba(0,0,0,0.15);
                    animation: fadeIn 1s ease-in-out;
                }
                .card img {
                    width: 120px;
                    margin-bottom: 20px;
                }
                .card h1 {
                    color: #28a745;
                    font-size: 2.2rem;
                    margin-bottom: 10px;
                }
                .card p {
                    font-size: 1rem;
                    color: #555;
                }
                @keyframes fadeIn {
                    from { opacity: 0; transform: translateY(-20px); }
                    to { opacity: 1; transform: translateY(0); }
                }
            </style>
        </head>
        <body>
            <div class="card">
                <img src="https://nyc3.digitaloceanspaces.com/smtech-space/uploads/images-removebg-preview_1757588224_1521.png" alt="PayPal Logo">
                <h1>Payment Successful 🎉</h1>
                <p>Thank you for your payment via PayPal.</p>
            </div>
        </body>
        </html>
        """
        return HttpResponse(html_content)


def payment_fail(request):
    if request.method == 'GET':
        html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Success</title>
        <style>
            body {
                background-color: #ffffff;
                display: flex;
                justify-content: center;
                align-items: center;
                height: 100vh;
                margin: 0;
                font-family: Arial, sans-serif;
            }
            h1 {
                color: #dc3545; /* red */
                font-size: 2.5rem;
            }
        </style>
    </head>
    <body>
        <h1>Payment Failed</h1>
    </body>
    </html>
    """
        return HttpResponse(html_content)
