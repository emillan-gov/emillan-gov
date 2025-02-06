---
layout: default
title: "Projects"
permalink: /projects/
---

<h1>My Projects</h1>

<div class="projects-grid">
  {% for project in site.projects %}
    <div class="project-card">
      <div class="project-info">
        <h2>{{ project.title }}</h2>
        <p>{{ project.description }}</p>
        <div class="project-stack">
          {% for tech in project.stack %}
            <img src="/assets/icons/{{ tech }}.png" alt="{{ tech }}" class="stack-icon">
          {% endfor %}
        </div>
        <a href="{{ project.url }}" class="project-link">View Project →</a>
      </div>
      <div class="project-image-container">
        <img src="{{ project.image }}" alt="{{ project.title }}" class="project-image">
      </div>
    </div>
  {% endfor %}
</div>
