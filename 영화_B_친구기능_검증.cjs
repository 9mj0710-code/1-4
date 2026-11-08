const fs = require('fs'), vm = require('vm'), assert = require('assert');
const html = fs.readFileSync('영화_B_수정본2.html', 'utf8');
const code = html.match(/<script>([\s\S]*?)<\/script>/)[1];
const elements = new Map(), saved = new Map();
function element() { return {style:{}, value:'', textContent:'', disabled:false, children:[], classList:{contains:()=>false}, replaceChildren(){this.children=[];}, appendChild(child){this.children.push(child);}, addEventListener(name,fn){this[name]=fn;}, focus(){}}; }
const context = vm.createContext({console, structuredClone, crypto:require('crypto').webcrypto,
 location:{protocol:'http:'}, window:{addEventListener(){}},
 document:{getElementById(id){if(!elements.has(id)) elements.set(id,element()); return elements.get(id);},querySelector(){return context.document.getElementById('header');},createElement:element},
 localStorage:{getItem:k=>saved.get(k)||null,setItem:(k,v)=>saved.set(k,v)}});
vm.runInContext(code,context);
vm.runInContext(`
let latestFeed = [];
renderFeed = filter => { latestFeed = visibleFeedUsers(filter); };
openModal = () => {}; closeModal = () => {}; showToast = () => {};
authRequest = async () => ({user: googleUser});
`,context);
async function run(source){return vm.runInContext(source,context);}
(async()=>{
 assert.equal(await run("visibleFeedUsers('all').length"),1);
 assert.equal(await run("visibleFeedUsers('friends').length"),0);
 await run("displayGoogleUser({id:'accountA',name:'A'})");
 assert.equal(await run("visibleFeedUsers('all').length"),1);
 await run("document.getElementById('friendNicknameInput').value=''; searchDemoFriend({preventDefault(){}})");
 assert.equal(await run('demoFriends.length'),0);
 await run("document.getElementById('friendNicknameInput').value='<친구&테스트>'; searchDemoFriend({preventDefault(){}}); document.getElementById('friendSearchResults').children[0].click()");
 assert.equal(await run('pendingFriend.name'),'<친구&테스트>');
 assert.equal(await run('demoFriends.length'),0); // selection or cancellation does not add
 await run('acceptDemoFriend()');
 assert.equal(await run("visibleFeedUsers('friends').length"),1);
 assert.equal(await run("visibleFeedUsers('all').length"),2);
 await run("searchDemoFriend({preventDefault(){}})");
 assert.equal(await run("document.getElementById('friendSearchResults').children[0].disabled"),true);
 await run('logoutGoogle()');
 assert.equal(await run("visibleFeedUsers('friends').length"),0);
 assert.equal(await run("visibleFeedUsers('all').length"),1);
 await run("displayGoogleUser({id:'accountB',name:'B'})");
 assert.equal(await run('demoFriends.length'),0);
 await run("displayGoogleUser({id:'accountA',name:'A'})");
 assert.equal(await run('demoFriends.length'),1);
 await run("document.getElementById('friendNicknameInput').value='Expired'; searchDemoFriend({preventDefault(){}}); document.getElementById('friendSearchResults').children[0].click(); authRequest=async()=>({user:null}); prepareGoogleLogin=()=>{};");
 await run('acceptDemoFriend()');
 assert.equal(await run('googleUser'),null);
 assert.equal(await run("visibleFeedUsers('friends').length"),0);
 console.log('PASS: public-only before friendship, empty search, safe nickname, confirmation, add, duplicate prevention, logout hiding, account isolation, restore, expired-session rejection.');
})().catch(error=>{ console.error(error);process.exitCode=1; });
