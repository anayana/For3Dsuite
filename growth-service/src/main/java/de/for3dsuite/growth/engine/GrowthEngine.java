package de.for3dsuite.growth.engine;

import de.for3dsuite.growth.model.Dtos.SimulateRequest;
import de.for3dsuite.growth.model.Dtos.SimulationResult;

/**
 * Abstraktion ueber die eigentliche Wachstumssimulation. Zwei Implementierungen:
 *
 *  - {@link StubGrowthEngine}      deterministischer Platzhalter, laeuft ohne die
 *                                  GPL-JAR (Entwicklung, Tests, Demo).
 *  - {@link TreeGrossGrowthEngine} bindet die echte TreeGrOSS/BWINPro-Engine ein
 *                                  (GPLv3; JAR separat, siehe README).
 *
 * Auswahl ueber die Property {@code growth.engine} (stub | treegross).
 */
public interface GrowthEngine {
    SimulationResult simulate(SimulateRequest request);

    /** Name der aktiven Engine (fuer /health und Logging). */
    String name();
}
