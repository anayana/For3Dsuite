package de.for3dsuite.growth.engine;

import de.for3dsuite.growth.model.Dtos.Period;
import de.for3dsuite.growth.model.Dtos.ProjectedTree;
import de.for3dsuite.growth.model.Dtos.SimulateRequest;
import de.for3dsuite.growth.model.Dtos.SimulateSpec;
import de.for3dsuite.growth.model.Dtos.SimulationResult;
import de.for3dsuite.growth.model.Dtos.Tree;

import java.time.Year;
import java.util.ArrayList;
import java.util.List;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Component;

/**
 * Platzhalter-Engine OHNE TreeGrOSS: einfaches, deterministisches Wachstum, damit
 * der Dienst und der End-zu-End-Fluss (Pipeline -> Dienst -> Viewer) auch ohne die
 * GPL-JAR lauffaehig und testbar sind. KEIN wissenschaftliches Modell -- nur ein
 * lineares Demonstrator-Wachstum. Fuer belastbare Prognosen die echte Engine
 * ({@link TreeGrossGrowthEngine}) aktivieren.
 *
 * Spiegelt bewusst die Formel des Python-Stubs (Round-Trip-Test) wider:
 *   BHD += 0.35 cm/Jahr, Hoehe += 0.18 m/Jahr; kleine Baeume scheiden spaet aus.
 */
@Component
@ConditionalOnProperty(name = "growth.engine", havingValue = "stub", matchIfMissing = true)
public class StubGrowthEngine implements GrowthEngine {

    private static final double DBH_PER_YEAR = 0.35;
    private static final double HEIGHT_PER_YEAR = 0.18;

    @Override
    public SimulationResult simulate(SimulateRequest req) {
        SimulateSpec spec = req.simulate() != null ? req.simulate()
                : new SimulateSpec(20, 5);
        int years = spec.years() != null ? spec.years() : 20;
        int step = spec.step_years() != null && spec.step_years() > 0 ? spec.step_years() : 5;
        int base = Year.now().getValue();

        List<Period> periods = new ArrayList<>();
        for (int s = 0; s <= years; s += step) {
            List<ProjectedTree> trees = new ArrayList<>();
            for (Tree t : req.trees()) {
                double dbh0 = t.dbh_cm() != null ? t.dbh_cm() : 0;
                double h0 = t.height_m() != null ? t.height_m() : 0;
                boolean alive = !(dbh0 < 10 && s >= 15);
                trees.add(new ProjectedTree(
                        t.id(),
                        round1(dbh0 + DBH_PER_YEAR * s),
                        round1(h0 + HEIGHT_PER_YEAR * s),
                        alive,
                        !alive));
            }
            periods.add(new Period(base + s, trees));
        }
        return new SimulationResult(req.stand(), periods);
    }

    @Override
    public String name() {
        return "stub";
    }

    private static double round1(double v) {
        return Math.round(v * 10.0) / 10.0;
    }
}
