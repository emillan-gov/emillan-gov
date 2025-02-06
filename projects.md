---
layout: default
title: "Projects"
---

<h1>My Projects</h1>

<ul>
  {% for project in site.projects %}
    <li>
      <a href="{{ project.url }}">{{ project.title }}</a> - {{ project.description }}
    </li>
  {% endfor %}
</ul>

