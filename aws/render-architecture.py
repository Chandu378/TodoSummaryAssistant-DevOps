#!/usr/bin/env python3
"""Regenerate the architecture PNG with Pillow (pip install Pillow)."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import math

HERE = Path(__file__).resolve().parent
image = Image.new('RGB', (1800, 1160), '#f4f7fb')
draw = ImageDraw.Draw(image)
font_paths = ['/System/Library/Fonts/Supplemental/Arial.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf']
font_path = next((path for path in font_paths if Path(path).exists()), None)


def font(size):
    return ImageFont.truetype(font_path, size) if font_path else ImageFont.load_default(size=size)


def box(bounds, title, lines, fill='#ffffff', color='#172b4d'):
    draw.rounded_rectangle(bounds, radius=16, fill=fill, outline='#9eafc4', width=2)
    x, y = bounds[0]+22, bounds[1]+20
    draw.text((x, y), title, fill=color, font=font(25))
    for index, line in enumerate(lines):
        draw.text((x, y+46+index*30), line, fill='#344d6e', font=font(20))


def arrow(start, end, label=None, position=None):
    draw.line([start, end], fill='#4776a6', width=4)
    angle = math.atan2(end[1]-start[1], end[0]-start[0])
    points = [end] + [(end[0]-17*math.cos(angle+delta), end[1]-17*math.sin(angle+delta)) for delta in [-0.45, 0.45]]
    draw.polygon(points, fill='#4776a6')
    if label:
        draw.text(position or ((start[0]+end[0])/2, (start[1]+end[1])/2), label, fill='#344d6e', font=font(19))


draw.text((55, 32), 'Todo Summary Assistant | AWS delivery and operations', fill='#102641', font=font(38))
draw.text((55, 84), 'EC2 + private RDS | OIDC delivery, health checks and monitoring', fill='#54708f', font=font(22))
box((55, 150, 425, 325), 'GitHub Actions', ['Java + React tests', 'Docker/MySQL smoke checks', 'Full SHA release tags'])
box((500, 150, 875, 325), 'IAM delivery role / OIDC', ['Trust only this repo + main', 'Scoped ECR, S3 and SSM', 'No stored AWS access keys'], '#e8f0ff')
box((950, 150, 1310, 325), 'ECR + private S3', ['Immutable application images', 'Versioned config + checksum', 'Retained rollback releases'], '#e8f0ff')
box((1380, 150, 1745, 325), 'Secrets Manager', ['RDS-managed DB credential', 'App keys + Grafana password', 'Optional alert webhook'], '#fff2df')
arrow((425, 235), (500, 235))
arrow((875, 235), (950, 235))

draw.rounded_rectangle((45, 410, 1755, 970), radius=22, fill='#e7edf4', outline='#8ca5c2', width=3)
draw.text((65, 425), 'Dedicated VPC | 10.20.0.0/16', fill='#244261', font=font(24))
draw.rounded_rectangle((70, 485, 1220, 940), radius=18, fill='#edf7fc', outline='#8cb6c9', width=2)
draw.text((90, 500), 'Public subnet / EC2 (Amazon Linux 2023)', fill='#244261', font=font(24))
box((95, 555, 430, 765), 'Nginx frontend', ['TCP 80: reviewer CIDR only', 'React static assets', '/api proxy + /readyz', 'Non-root UID 101'])
box((495, 555, 820, 765), 'Spring Boot backend', ['8080 API / 8081 management', 'DB-inclusive readiness', 'Prometheus histograms', 'Non-root UID 10001'])
box((885, 555, 1195, 765), 'Monitoring containers', ['Prometheus + Grafana', 'Node + Blackbox exporters', 'Alertmanager', 'Admin ports: localhost only'])
arrow((430, 650), (495, 650))
arrow((885, 650), (820, 650), 'scrape', (835, 622))
box((95, 800, 625, 930), 'EC2 role + SSM release launcher', ['Pull images / read secrets via instance role', 'Host lock, health gates and previous-release rollback'], '#e2efff')
box((685, 800, 1195, 930), 'Host metrics timer', ['Docker restart / uptime textfile every 15 sec', 'No monitoring access to the Docker socket'], '#e2efff')
box((1270, 555, 1725, 845), 'Private RDS MySQL 8.4', ['Two isolated DB subnets / two AZs', '3306 from EC2 SG only', 'No public accessibility', 'Encrypted storage + TLS transport', '7-day backups + final snapshot', 'Optional Multi-AZ'], '#fff2df')
arrow((820, 750), (1270, 750), 'Private MySQL 3306 / TLS', (940, 775))
arrow((1080, 325), (1080, 485), 'SSM / pull artifacts', (1100, 365))
arrow((1500, 325), (1500, 410), 'Role-based retrieval', (1520, 360))

draw.text((65, 1000), 'Administration: SSM Session Manager; no inbound SSH. IMDSv2 required, hop limit 1.', fill='#344d6e', font=font(23))
draw.text((65, 1040), 'Grafana 3001 / Prometheus 9090 / Alertmanager 9093 accessed through SSM tunnels.', fill='#344d6e', font=font(23))
draw.text((65, 1080), 'Single EC2 assessment footprint: external host monitoring and HA are follow-up hardening.', fill='#344d6e', font=font(23))
image.save(HERE / 'architecture-diagram.png')
