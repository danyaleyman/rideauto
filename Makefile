# Windows (PowerShell): .\deploy.ps1 -m "описание"  |  .\quick.ps1
.PHONY: deploy quick
deploy:
	git add .
	git commit -m "$(m)"
	git push server main
	ssh rideauto "cd /opt/rideauto && git pull && docker compose up -d --build web"

quick:
	git add .
	git commit -m "quick update"
	git push server main
