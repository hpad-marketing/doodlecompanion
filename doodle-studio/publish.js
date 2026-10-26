// Publish a Doodle Studio build to this update channel.
//   node doodle-studio/publish.js <build folder> <version> "notes" [runtime]
// <build folder> holds "Doodle Studio.exe" and desktop/. Only the EXE and
// desktop/resources/app/* are published; the bundled Electron runtime is too big
// for GitHub and only its version is recorded. Files are stored gzip'd and named
// by content hash, so unchanged files cost nothing on the next publish.
const fs=require('fs'),path=require('path'),crypto=require('crypto'),zlib=require('zlib');
const [build,version,notes='',runtimeArg]=process.argv.slice(2);
if(!build||!version)throw Error('usage: publish.js <build folder> <version> "notes" [runtime]');
const here=__dirname,files={};
const list=['Doodle Studio.exe',...fs.readdirSync(path.join(build,'desktop/resources/app'),{recursive:true}).map(f=>'desktop/resources/app/'+f.split(path.sep).join('/')).filter(f=>fs.statSync(path.join(build,f)).isFile())];
fs.mkdirSync(path.join(here,'files'),{recursive:true});
for(const f of list){const data=fs.readFileSync(path.join(build,f)),sha256=crypto.createHash('sha256').update(data).digest('hex'),gz='files/'+sha256+'.gz';
  if(!fs.existsSync(path.join(here,gz)))fs.writeFileSync(path.join(here,gz),zlib.gzipSync(data,{level:9}));files[f]={sha256,size:data.length,gz};}
let runtime=runtimeArg;try{runtime=runtime||fs.readFileSync(path.join(build,'desktop/version'),'utf8').trim();}catch{}
if(!runtime)throw Error('runtime version unknown; pass it as the 4th argument');
// Drop blobs no manifest points at any more.
const keep=new Set(Object.values(files).map(f=>path.basename(f.gz)));
for(const name of fs.readdirSync(path.join(here,'files')))if(!keep.has(name))fs.unlinkSync(path.join(here,'files',name));
fs.writeFileSync(path.join(here,'manifest.json'),JSON.stringify({version,notes,runtime,published:new Date().toISOString(),files},null,1)+'\n');
console.log(version,Object.keys(files).length+' files');
