import test from 'node:test';
import assert from 'node:assert/strict';
import {relatedRows} from '../../src/backtesting_api/web/backtest-data.mjs';

test('all open lots are displayed and selected entry links only its own lot', () => {
    const a = {position_id: 'A', entry_fill_id: 'fa'}, b = {position_id: 'B', entry_fill_id: 'fb'};
    const run = {open_position: null, open_positions: [a, b],
        fills: [{fill_id: 'fa', fill_time: '2026-03-25T09:05:00+07:00', order_id: 'oa'}],
        orders: [{order_id: 'oa', signal_id: 'sa'}], signals: [{signal_id: 'sa'}], trades: [], equity_history: []};
    assert.deepEqual(relatedRows(run).position, [a, b]);
    assert.deepEqual(relatedRows(run, 'fa').position, [a]);
    assert.deepEqual(relatedRows({...run, open_positions: undefined, open_position: a}).position, [a]);
});
