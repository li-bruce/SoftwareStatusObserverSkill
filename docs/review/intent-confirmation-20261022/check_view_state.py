"""Use real graph controls; verify identity and project-local view persistence across phases."""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).parent
sys.path.insert(0,str(ROOT/'.validation/browser-python'))
from playwright.sync_api import sync_playwright


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage',choices=['seed','verify'])
    parser.add_argument('--url',default='http://127.0.0.1:8866')
    parser.add_argument('--label',required=True)
    args=parser.parse_args()
    out=OUT/'browser'/args.label;out.mkdir(parents=True,exist_ok=False)
    report={'stage':args.stage,'url':args.url,'checks':[],'errors':[]}
    def passed(name,**details):report['checks'].append({'name':name,'passed':True,**details})
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='chrome',headless=True)
        page=browser.new_page(viewport={'width':1440,'height':1000})
        page.on('pageerror',lambda error:report['errors'].append(str(error)))
        try:
            page.goto(args.url+'/graph',wait_until='domcontentloaded')
            try:page.wait_for_load_state('networkidle',timeout=1500)
            except Exception:pass
            page.wait_for_function('window.graphDebug?.graph?.boxes?.length > 0')
            if args.stage=='seed':
                before=page.request.get(args.url+'/api/preferences').json()
                (out/'preferences-before.json').write_text(json.dumps(before,ensure_ascii=False,indent=2),encoding='utf8')
                if page.locator('#discussion-clear').is_visible():page.click('#discussion-clear')
                page.select_option('#analysis-view','overview');page.click('#collapse');page.click('#fit')
                node=page.locator('#semantic [data-node-id="derive_project"]')
                node.focus()
                position=page.evaluate('(()=>{const b=graphDebug.graph.byId.get("derive_project");return {x:b.x,y:b.y};})()')
                x=float(node.get_attribute('data-screen-x'));y=float(node.get_attribute('data-screen-y'))
                page.mouse.move(x,y);page.mouse.down();page.mouse.move(x+76,y-32,steps=8);page.mouse.up()
                page.wait_for_function('document.querySelector("#layout-status").textContent.includes("已保存到项目")')
                moved=page.evaluate('(()=>{const b=graphDebug.graph.byId.get("derive_project");return {x:b.x,y:b.y};})()')
                assert abs(moved['x']-position['x'])>5 and abs(moved['y']-position['y'])>5,(position,moved)
                passed('node_drag_changes_position',before=position,after=moved)
                node.focus();page.click('#annotate')
                page.fill('#node-name','派生项目（审查标记）')
                page.fill('#node-note','检查派生类型与空数据；此批注不是业务规则。')
                page.check('#node-core');page.click('#annotation-form button[type="submit"]')
                page.wait_for_function('async()=>Object.values((await (await fetch("/api/preferences")).json()).entries).some(s=>s.includes("审查标记"))')
                expected={'id':'derive_project','label':'派生项目（审查标记）','note':'检查派生类型与空数据；此批注不是业务规则。','position':moved}
                (OUT/'view-expected.json').write_text(json.dumps(expected,ensure_ascii=False,indent=2),encoding='utf8')
                page.reload(wait_until='domcontentloaded')
            expected=json.loads((OUT/'view-expected.json').read_text(encoding='utf8'))
            page.wait_for_function('document.querySelector("#semantic [data-node-id=derive_project]")?.textContent.includes("审查标记")')
            node=page.locator('#semantic [data-node-id="derive_project"]')
            assert node.get_attribute('data-core')=='true'
            actual=page.evaluate('(()=>{const b=graphDebug.graph.byId.get("derive_project");return {x:b.x,y:b.y};})()')
            assert abs(actual['x']-expected['position']['x'])<0.1 and abs(actual['y']-expected['position']['y'])<0.1,(actual,expected['position'])
            preferences=page.request.get(args.url+'/api/preferences').json()
            assert any(expected['note'] in value for value in preferences['entries'].values())
            passed('label_note_core_and_position_persist',position=actual,revision=preferences['revision'])
            node.focus()
            was_open=page.locator('#node-expand').inner_text()=='收起'
            if was_open:
                page.click('#node-expand')
                page.wait_for_function('document.querySelector("#semantic [data-node-id=derive_project]")?.dataset.representation === "node"')
                node.focus()
            page.click('#node-expand');page.click('#fit')
            page.wait_for_function('["circle","self"].includes(document.querySelector("#semantic [data-node-id=derive_project]")?.dataset.representation)')
            passed('same_node_expands_to_region',previously_open=was_open)
            page.screenshot(path=str(out/'graph.png'),full_page=True)
            report['graph']=page.evaluate('({model_nodes:graphDebug.view.model.nodes.map(n=>n.id),stage:graphDebug.view.stage,metrics:graphDebug.metrics})')
            (out/'preferences.json').write_text(json.dumps(preferences,ensure_ascii=False,indent=2),encoding='utf8')
        except Exception as error:
            report['failure']=repr(error)
            page.screenshot(path=str(out/'failure.png'),full_page=True)
        finally:
            report['passed']=not report.get('failure') and not report['errors']
            (out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
            browser.close()
    print(json.dumps({k:v for k,v in report.items() if k not in {'graph'}},ensure_ascii=True))
    raise SystemExit(0 if report['passed'] else 1)


if __name__=='__main__':main()
