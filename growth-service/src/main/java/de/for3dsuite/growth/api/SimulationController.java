package de.for3dsuite.growth.api;

import de.for3dsuite.growth.engine.GrowthEngine;
import de.for3dsuite.growth.model.Dtos.SimulateRequest;
import de.for3dsuite.growth.model.Dtos.SimulationResult;

import java.util.List;
import java.util.Map;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

/**
 * HTTP-Schnittstelle des Wachstumsdienstes.
 *
 *   POST /simulate   Baumliste + Bestand (+ simulate-Block) rein, Zukunftsbestaende raus
 *   GET  /health     aktive Engine + Bereitschaft
 */
@RestController
public class SimulationController {

    private final GrowthEngine engine;

    public SimulationController(GrowthEngine engine) {
        this.engine = engine;
    }

    @PostMapping("/simulate")
    public ResponseEntity<SimulationResult> simulate(@RequestBody SimulateRequest request) {
        if (request.trees() == null || request.trees().isEmpty()) {
            return ResponseEntity.badRequest().build();
        }
        return ResponseEntity.ok(engine.simulate(request));
    }

    @GetMapping("/health")
    public Map<String, Object> health() {
        return Map.of("status", "ok", "engine", engine.name());
    }
}
