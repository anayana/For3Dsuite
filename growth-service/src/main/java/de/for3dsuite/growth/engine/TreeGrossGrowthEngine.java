package de.for3dsuite.growth.engine;

import de.for3dsuite.growth.model.Dtos.SimulateRequest;
import de.for3dsuite.growth.model.Dtos.SimulationResult;

import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Component;

/**
 * Adapter auf die echte TreeGrOSS/BWINPro-Engine (GPLv3). Diese Klasse ist die
 * EINZIGE Nahtstelle, an der GPL-Code beruehrt wird -- bewusst duenn gehalten.
 *
 * Aktivierung:
 *   1. TreeGrOSS-JAR unter growth-service/lib/treegross.jar ablegen
 *      (Bezug/Lizenz siehe README; NICHT im Repo mitgeliefert).
 *   2. In pom.xml das system-scope-Dependency einschalten.
 *   3. application.properties: growth.engine=treegross
 *
 * Der Mapping-Aufbau (Pseudocode, an die konkrete TreeGrOSS-API anzupassen):
 *
 *   Stand st = new Stand();
 *   st.setEcoRegion(...); st.setSiteIndex(request.stand().site_index());
 *   st.year = request.stand().age_years();
 *   for (Tree t : request.trees()) {
 *       st.addTree(t.species(), t.id(), t.age_years(), t.dbh_cm(),
 *                  t.height_m(), t.crown_base_m(), t.x(), t.y(), out_of_stand);
 *   }
 *   for (int s = 0; s <= years; s += step) {
 *       // Zwischenzustand in eine Period uebernehmen
 *       st.grow(step);   // TreeGrOSS-Wachstumsschritt
 *   }
 *
 * Die Artcodes (species) und Feldnamen muessen zur SpeciesDef/Version der
 * eingesetzten TreeGrOSS-Distribution passen (siehe SPECIES-Map in
 * scripts/treegross_export.py).
 */
@Component
@ConditionalOnProperty(name = "growth.engine", havingValue = "treegross")
public class TreeGrossGrowthEngine implements GrowthEngine {

    @Override
    public SimulationResult simulate(SimulateRequest request) {
        // TODO: echte TreeGrOSS-Simulation einbinden (siehe Klassen-Doku).
        // Bis die GPL-JAR vorliegt, bleibt diese Engine bewusst inaktiv, damit
        // versehentliches Aktivieren nicht still falsche Ergebnisse liefert.
        throw new UnsupportedOperationException(
                "TreeGrOSS-Engine noch nicht verdrahtet: JAR unter lib/treegross.jar "
                + "ablegen, pom.xml-Dependency und das Mapping in dieser Klasse "
                + "aktivieren (siehe README).");
    }

    @Override
    public String name() {
        return "treegross";
    }
}
