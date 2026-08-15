from html.parser import HTMLParser
from pathlib import Path

html = Path('dist/index.html').read_text(encoding='utf-8')

class Inspector(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack=[]
        self.buttons=[]
        self.forms=[]
        self.nested_forms=[]
        self.current_button=None
    def handle_starttag(self, tag, attrs):
        a=dict(attrs)
        if tag=='form':
            parent_form=next((x for x in reversed(self.stack) if x[0]=='form'),None)
            if parent_form:
                self.nested_forms.append((parent_form[1],a))
            self.forms.append(a)
        node=[tag,a]
        self.stack.append(node)
        if tag=='button':
            form=next((x[1] for x in reversed(self.stack[:-1]) if x[0]=='form'),None)
            self.current_button={'attrs':a,'form':form,'text':[]}
    def handle_data(self,data):
        if self.current_button is not None:
            self.current_button['text'].append(data)
    def handle_endtag(self,tag):
        if tag=='button' and self.current_button is not None:
            self.current_button['text']=' '.join(''.join(self.current_button['text']).split())
            self.buttons.append(self.current_button)
            self.current_button=None
        for i in range(len(self.stack)-1,-1,-1):
            if self.stack[i][0]==tag:
                del self.stack[i:]
                break

p=Inspector(); p.feed(html)
keywords=('返回','取消','保存','开户','广告数据','关闭')
print('UI_ACTION_DIAGNOSTICS_BEGIN')
print('forms=',len(p.forms),'nested_forms=',len(p.nested_forms))
for i,(outer,inner) in enumerate(p.nested_forms,1):
    print('NESTED_FORM',i,'outer=',outer,'inner=',inner)
for b in p.buttons:
    text=b['text']
    attrs=b['attrs']
    event=attrs.get('@click') or attrs.get('v-on:click') or ''
    if any(k in text for k in keywords) or any(k in event for k in ('showOpeningModal','showProviderModal','showAdDataModal','navigateTo')):
        print('BUTTON',repr(text),'type=',attrs.get('type','<default-submit>'),'click=',repr(event),'form_submit=',repr((b['form'] or {}).get('@submit.prevent') or (b['form'] or {}).get('v-on:submit.prevent') or 'NONE'))

checks={
 'opening_form': '@submit.prevent="saveOpeningDeal"',
 'provider_form': '@submit.prevent="saveOpeningProvider"',
 'ad_data_form': '@submit.prevent="saveAdDataRecord"',
 'opening_cancel': '@click="showOpeningModal=false"',
 'provider_close': '@click="showProviderModal=false"',
 'ad_data_close': '@click="showAdDataModal=false"',
}
for name,needle in checks.items(): print('CHECK',name,html.count(needle))
print('UI_ACTION_DIAGNOSTICS_END')
