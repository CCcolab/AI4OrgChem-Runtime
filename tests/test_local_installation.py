"""Engineering refusals for the clean source installer; no scientific imports."""
import importlib.util
import io
from pathlib import Path
import zipfile
import pytest

spec = importlib.util.spec_from_file_location('local_installer', Path(__file__).parents[1]/'scripts/install-local-runtime.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)


@pytest.mark.parametrize('name', ['../evil', '/root/evil', 'a/../evil', 'C:/evil', 'a\\evil', 'a//evil'])
def test_source_path_refused(name):
    with pytest.raises(ValueError): m.safe_path(name)


def test_existing_destination_preserved(tmp_path):
    existing = tmp_path/'existing'; existing.mkdir(); marker = existing/'marker'; marker.write_text('keep')
    with pytest.raises(ValueError): m.new_directory(existing)
    assert marker.read_text() == 'keep'


def test_tar_traversal_member_refused_before_write(tmp_path):
    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w') as z: z.writestr('../outside', b'bad')
    with pytest.raises(ValueError): m.unpack(out.getvalue(), tmp_path)
    assert not (tmp_path.parent/'outside').exists()


def test_fixed_public_base_and_only_host_rebind():
    assert m.PUBLIC_BASE.endswith('@sha256:4766d8b510c428e595d74b9cc5bbb2fae8e26316fffb4adc89908d79aacd58a2')
    assert m.HOST_OVERRIDES == {'scripts/run-high-cost-case.py', 'tests/test_high_cost_supervisor.py',
                               'scripts/run-molecular-service.py', 'scripts/run-registered-case.py',
                               'scripts/run-protocol-case.py'}
