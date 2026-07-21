package de.for3dsuite.growth;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import de.for3dsuite.growth.engine.StubGrowthEngine;
import de.for3dsuite.growth.model.Dtos.Period;
import de.for3dsuite.growth.model.Dtos.SimulateRequest;
import de.for3dsuite.growth.model.Dtos.SimulateSpec;
import de.for3dsuite.growth.model.Dtos.SimulationResult;
import de.for3dsuite.growth.model.Dtos.Stand;
import de.for3dsuite.growth.model.Dtos.Tree;
import java.time.Year;
import java.util.List;
import org.junit.jupiter.api.Test;

class StubGrowthEngineTest {

    @Test
    void grows_dbh_and_height_over_periods() {
        var stand = new Stand("s", 0.07, 200, 32.0, 46.5, 11.4);
        var big = new Tree("t1", 511, 50.0, 25.0, 1.0, 2.0, null, null, false);
        var small = new Tree("t2", 511, 8.0, 6.0, 3.0, 4.0, null, null, false);
        var req = new SimulateRequest(stand, new SimulateSpec(20, 5), List.of(big, small));

        SimulationResult res = new StubGrowthEngine().simulate(req);

        List<Period> p = res.periods();
        assertEquals(5, p.size());                  // 0,5,10,15,20
        // Basisjahr ist das aktuelle Jahr -> relativ pruefen, nicht fest verdrahten
        int base = Year.now().getValue();
        assertEquals(base, p.get(0).year());
        assertEquals(base + 20, p.get(4).year());
        var last = p.get(4).trees().get(0);
        assertTrue(last.dbh_cm() > 50.0);           // gewachsen
        assertTrue(last.height_m() > 25.0);
        // kleiner Baum scheidet spaet aus
        var small_last = p.get(4).trees().get(1);
        assertFalse(small_last.alive());
        assertTrue(small_last.removed());
    }
}
