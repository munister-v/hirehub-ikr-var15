"""Навантаження (за бажанням): locust -f docs/locustfile.py --host http://localhost:8080 — не запускалося в межах роботи."""
from locust import HttpUser, between, task


class Browser(HttpUser):
    wait_time = between(0.5, 2)

    @task(5)
    def vacancies(self):
        self.client.get('/api/vacancies/?search=python')

    @task(2)
    def catalog(self):
        self.client.get('/')

    @task(1)
    def health(self):
        self.client.get('/matching/health')
