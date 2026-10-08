package com.todoapp;

import com.todoapp.entity.Todo;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.autoconfigure.actuate.observability.AutoConfigureObservability;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.boot.test.web.server.LocalManagementPort;
import org.springframework.http.HttpStatus;
import org.springframework.test.context.ActiveProfiles;

import static org.assertj.core.api.Assertions.assertThat;

@ActiveProfiles("test")
@AutoConfigureObservability
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class OperationsIntegrationTests {
    @Autowired
    private TestRestTemplate http;

    @LocalManagementPort
    private int managementPort;

    @Test
    void healthMetricsAndDatabaseBackedCrudWork() {
        assertThat(http.getForEntity("/livez", String.class).getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(http.getForEntity("/readyz", String.class).getStatusCode()).isEqualTo(HttpStatus.OK);
        Todo input = new Todo(null, "Verify delivery", "DevOps smoke test", false);
        var created = http.postForEntity("/api/todos", input, Todo.class);
        assertThat(created.getStatusCode()).isEqualTo(HttpStatus.CREATED);
        Todo todo = created.getBody();
        assertThat(todo).isNotNull();
        assertThat(todo.getId()).isPositive();
        todo.setCompleted(true);
        http.put("/api/todos/" + todo.getId(), todo);
        assertThat(http.getForObject("/api/todos", Todo[].class))
                .anySatisfy(saved -> {
                    assertThat(saved.getId()).isEqualTo(todo.getId());
                    assertThat(saved.isCompleted()).isTrue();
                });
        http.delete("/api/todos/" + todo.getId());
        assertThat(http.getForObject("/api/todos", Todo[].class))
                .noneMatch(saved -> saved.getId().equals(todo.getId()));
        var metrics = http.getForEntity("http://localhost:" + managementPort + "/actuator/prometheus", String.class);
        assertThat(metrics.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(metrics.getBody()).contains("http_server_requests_seconds_count", "http_server_requests_seconds_bucket");
        assertThat(http.getForEntity("/actuator/prometheus", String.class).getStatusCode()).isEqualTo(HttpStatus.NOT_FOUND);
    }
}
